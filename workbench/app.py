"""Authenticated, route-allowlisted observer; B credentials never cross this boundary."""
from contextlib import asynccontextmanager
import hashlib
import json
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx
from pydantic import Field

from actuarial.research_scenario import load_research_scenario
from contracts import models as m
from workbench.bscale_batches import BScaleBatchManager, BatchAlreadyRunning
from workbench.integration_results import IntegrationResults
from workbench.real_runs import RealRunAlreadyRunning, RealRunManager, RealRunNotAuthorized

ROOT = Path(__file__).resolve().parents[1]
COOKIE = "agentshield_observer"


def local_origin(value):
    url = urlsplit(value)
    if (url.scheme != "http" or url.hostname != "127.0.0.1" or not url.port
            or url.path or url.query or url.fragment or url.username or url.password):
        raise ValueError("Explicit 127.0.0.1 HTTP origin required")
    return value


class ObserverError(Exception):
    def __init__(self, code, status):
        self.code, self.status = code, status


class Authority:
    """A one-use local launcher grant, then an HttpOnly observer cookie. No B scope."""
    def __init__(self, grant):
        self.grant_hash = self.digest(grant)
        self.grant_until = time.monotonic() + 120
        self.sessions = {}
        self.lock = threading.Lock()

    @staticmethod
    def digest(value):
        return hashlib.sha256(value.encode()).hexdigest()

    def exchange(self, grant):
        with self.lock:
            if (time.monotonic() > self.grant_until or self.grant_hash is None
                    or not secrets.compare_digest(self.grant_hash, self.digest(grant))):
                raise ObserverError("LOCAL_APPROVAL_REQUIRED", 401)
            self.grant_hash = None
            token = secrets.token_urlsafe(32)
            self.sessions[self.digest(token)] = time.monotonic() + 3600
            return token

    def check(self, token):
        with self.lock:
            if self.sessions.get(self.digest(token or ""), 0) <= time.monotonic():
                raise ObserverError("LOCAL_APPROVAL_REQUIRED", 401)

    def revoke(self, token):
        with self.lock:
            self.sessions.pop(self.digest(token or ""), None)


class Pair(m.Wire):
    grant: str = Field(min_length=32, max_length=128)


class CreateDevelopmentRun(m.Wire):
    fixture_id: m.FixtureId


class StartRealRun(m.Wire):
    count: int = Field(ge=1, le=10)


def create_observer(base_url, admin_token, grant, *, origin="http://127.0.0.1:8810",
                    tenant_id="workbench-development", frontend_dir=None, transport=None,
                    dev_origin=None, integration_root=None, batch_manager=None,
                    bscale_batch_size=100, real_run_manager=None):
    local_origin(base_url)
    origins = {local_origin(origin)}
    if dev_origin:
        origins.add(local_origin(dev_origin))
    hosts = {urlsplit(value).netloc for value in origins}
    if len(admin_token) < 32 or len(grant) < 32:
        raise ValueError("Fresh private credentials required")
    # Validate operator configuration before making any network request.
    m.CreateSession(tenant_id=tenant_id)
    client = httpx.Client(base_url=base_url, headers={"Authorization": "Bearer " + admin_token},
                          timeout=5, trust_env=False, follow_redirects=False, transport=transport)
    authority = Authority(grant)
    results = IntegrationResults(Path(integration_root or ROOT / "artifacts/c_l0/runs"), ROOT)
    batches = batch_manager or BScaleBatchManager(
        ROOT, count=bscale_batch_size, on_complete=results.refresh_batch,
    )
    real_runs = real_run_manager or RealRunManager(ROOT, on_complete=results.refresh_batch)
    if real_run_manager is not None and getattr(real_run_manager, "on_complete", None) is None:
        # 注入式管理器（QA/测试）也要能刷新权威目录，否则新批次要等到下次重启才可见。
        real_run_manager.on_complete = results.refresh_batch

    @asynccontextmanager
    async def lifespan(app):
        yield
        client.close()

    app = FastAPI(title="Local development observer", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    app.state.authority = authority
    app.state.batch_manager = batches
    app.state.real_run_manager = real_runs

    @app.middleware("http")
    async def boundary(request, call_next):
        # Block DNS rebinding and cross-origin browser requests, including pairing.
        if request.headers.get("host") not in hosts:
            return JSONResponse({"code": "LOCAL_HOST_REQUIRED"}, status_code=403)
        if request.url.path.startswith("/observer/"):
            source = request.headers.get("origin")
            if ((source is not None and source not in origins)
                    or (request.method != "GET" and source not in origins)
                    or request.headers.get("x-workbench-request") != "1"
                    or request.headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none")):
                return JSONResponse({"code": "SAME_ORIGIN_REQUIRED"}, status_code=403)
        response = await call_next(request)
        response.headers.update({
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
        })
        return response

    @app.exception_handler(ObserverError)
    async def known_error(request, error):
        return JSONResponse({"code": error.code}, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def invalid(request, error):
        # Never echo invalid pairing bodies or credentials through validation errors.
        return JSONResponse({"code": "INVALID_REQUEST"}, status_code=422)

    @app.exception_handler(Exception)
    async def unexpected(request, error):
        return JSONResponse({"code": "OBSERVER_UNAVAILABLE"}, status_code=502)

    def authorized(request: Request):
        authority.check(request.cookies.get(COOKIE))

    def backend(method, path, model, *, params=None, body=None):
        try:
            result = client.request(method, path, params=params, json=body)
        except httpx.TimeoutException:
            raise ObserverError("B_TIMEOUT", 504) from None
        except httpx.HTTPError:
            raise ObserverError("B_UNAVAILABLE", 502) from None
        if result.status_code not in (200, 201):
            raise ObserverError("RUN_NOT_FOUND" if result.status_code == 404 else "B_UNAVAILABLE",
                                404 if result.status_code == 404 else 502)
        try:
            data = model.model_validate(result.json()).model_dump(mode="json")
        except (ValueError, TypeError):
            raise ObserverError("B_CONTRACT_MISMATCH", 502) from None
        # Defense in depth even if a upstream text field contains the admin secret.
        if admin_token in json.dumps(data, ensure_ascii=False):
            raise ObserverError("UNSAFE_UPSTREAM_DATA", 502)
        return data

    def evidence_in_scope(sid):
        data = backend("GET", f"/api/v1/admin/sessions/{sid}/evidence", m.EvidenceBundle)
        for key in ("initial_snapshot", "final_snapshot"):
            session = data[key]["session"]
            if session["tenant_id"] != tenant_id or session["session_id"] != sid:
                raise ObserverError("RUN_NOT_FOUND", 404)
        return data

    @app.post("/observer/pair")
    def pair(body: Pair):
        token = authority.exchange(body.grant)
        response = JSONResponse({"scope": "development_observer", "expires_in": 3600})
        response.set_cookie(COOKIE, token, httponly=True, samesite="strict", max_age=3600,
                            path="/observer", secure=False)  # Loopback HTTP only; never deployed.
        return response

    @app.post("/observer/logout", dependencies=[Depends(authorized)])
    def logout(request: Request):
        authority.revoke(request.cookies.get(COOKIE))
        response = JSONResponse({"logged_out": True})
        response.delete_cookie(COOKIE, path="/observer")
        return response

    @app.get("/observer/api/fixtures", dependencies=[Depends(authorized)])
    def fixtures():
        return backend("GET", "/api/v1/admin/fixtures", m.FixtureCatalog)

    @app.get("/observer/api/sessions", dependencies=[Depends(authorized)])
    def sessions(offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100)):
        return backend("GET", "/api/v1/admin/sessions", m.SessionPage,
                       params={"tenant_id": tenant_id, "offset": offset, "limit": limit})

    @app.post("/observer/api/sessions", dependencies=[Depends(authorized)], status_code=201)
    def create(body: CreateDevelopmentRun):
        data = backend("POST", "/api/v1/sessions", m.CreatedSession,
                       body={"tenant_id": tenant_id, "fixture_id": body.fixture_id,
                             "execution_source": "scripted_test", "experiment_id": "workbench-development",
                             "config_id": "unexecuted-development-session"})
        # This observer cannot operate tools; discard B's one-time run credential.
        return {"session": data["session"], "case_context": data["case_context"]}

    @app.get("/observer/api/sessions/{sid}/evidence", dependencies=[Depends(authorized)])
    def evidence(sid: m.Id):
        return evidence_in_scope(sid)

    @app.get("/observer/api/sessions/{sid}/events", dependencies=[Depends(authorized)])
    def events(sid: m.Id, after_seq: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100)):
        evidence_in_scope(sid)
        return backend("GET", f"/api/v1/admin/sessions/{sid}/events", m.EventPage,
                       params={"after_seq": after_seq, "limit": limit})

    @app.get("/observer/api/sessions/{sid}/ledger", dependencies=[Depends(authorized)])
    def ledger(sid: m.Id):
        evidence_in_scope(sid)
        return backend("GET", f"/api/v1/admin/sessions/{sid}/ledger", m.Ledger)

    @app.get("/observer/api/integration-runs", dependencies=[Depends(authorized)])
    def integration_runs():
        return results.catalog()

    @app.get("/observer/api/research-scenario", dependencies=[Depends(authorized)])
    def research_scenario():
        return load_research_scenario()

    @app.post("/observer/api/bscale-batches", dependencies=[Depends(authorized)], status_code=202)
    def start_bscale_batch():
        try:
            return app.state.batch_manager.start()
        except BatchAlreadyRunning:
            raise ObserverError("BATCH_ALREADY_RUNNING", 409) from None
        except (OSError, ValueError):
            raise ObserverError("BSCALE_SOURCE_UNAVAILABLE", 503) from None

    @app.get("/observer/api/bscale-batches/current", dependencies=[Depends(authorized)])
    def current_bscale_batch():
        return app.state.batch_manager.status()

    @app.get("/observer/api/bscale-batches/current/results", dependencies=[Depends(authorized)])
    def current_bscale_results():
        status = app.state.batch_manager.status()
        rows = [row for row in results.catalog()["runs"] if row["batch_id"] == status.get("batch_id")]
        return {"contract_version": "abcd-integration-0.1-candidate", "runs": rows}

    @app.post("/observer/api/real-runs", dependencies=[Depends(authorized)], status_code=202)
    def start_real_run(body: StartRealRun):
        try:
            return app.state.real_run_manager.start(body.count)
        except RealRunAlreadyRunning:
            raise ObserverError("REAL_RUN_ALREADY_RUNNING", 409) from None
        except RealRunNotAuthorized as error:
            return JSONResponse({"code": "REAL_RUN_NOT_AUTHORIZED", "reasons": error.reasons}, status_code=403)
        except (OSError, ValueError):
            raise ObserverError("REAL_RUN_UNAVAILABLE", 503) from None

    @app.get("/observer/api/real-runs/current", dependencies=[Depends(authorized)])
    def current_real_run():
        return app.state.real_run_manager.status()

    @app.get("/observer/api/integration-runs/{run_id}", dependencies=[Depends(authorized)])
    def integration_run(run_id: str):
        if len(run_id) != 20 or any(character not in "0123456789abcdef" for character in run_id):
            raise ObserverError("RUN_NOT_FOUND", 404)
        try:
            return results.detail(run_id)
        except KeyError:
            raise ObserverError("RUN_NOT_FOUND", 404) from None

    static = Path(frontend_dir or ROOT / "frontend/dist")
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="workbench")
    return app
