"""Local HTTP boundary. No evaluator, model provider, payments or paid-run entrypoints."""
import os
import hashlib
import math
from pathlib import Path
import re
import secrets
import sqlite3

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.exceptions import HTTPException

from contracts import models as m
from sandbox.fixture import REGISTRY, load_fixture
from sandbox.store import DomainError, Store, dumps, uid

bearer = HTTPBearer(auto_error=False)
ROOT = Path(__file__).resolve().parents[1]


def create_app(db_path=None, admin_token=None, *, initialize=True):
    if initialize:
        admin_token = admin_token or os.environ.get("AGENTSHIELD_ADMIN_TOKEN")
        if not admin_token or len(admin_token) < 32:
            raise RuntimeError("Set a fresh AGENTSHIELD_ADMIN_TOKEN with at least 32 characters.")
        if os.environ.get("ENABLE_PAID_RUNS", "false").lower() != "false" or os.environ.get("MAX_COST", "0") != "0":
            raise RuntimeError("This batch requires ENABLE_PAID_RUNS=false and MAX_COST=0.")
        store = Store(db_path or os.environ.get("AGENTSHIELD_DB", str(ROOT / "var/development.sqlite3")))
        store.initialize()
    else:
        store = None  # Schema export only; never serves requests.
    app = FastAPI(title="AgentShield B candidate sandbox", version=m.VERSION,
                  description="development_only fixtures; seven tools; execution source is caller-declared, not model-run proof")
    app.state.store = store

    @app.middleware("http")
    async def request_id(request, call_next):
        request.state.request_id = uid("request")
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        return response

    def audit_auth(request, error):
        store.security_event(request.state.request_id, error.code)
        raise error

    def admin(request: Request, credential: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credential is None:
            audit_auth(request, DomainError("UNAUTHORIZED", "Administrator credential required.", 401))
        if not secrets.compare_digest(credential.credentials, admin_token):
            audit_auth(request, DomainError("FORBIDDEN", "Administrator scope required.", 403))

    def session_auth(request: Request, session_id: str,
                     credential: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credential is None:
            audit_auth(request, DomainError("UNAUTHORIZED", "Session credential required.", 401))
        try:
            store.authenticate(session_id, credential.credentials)
        except DomainError as error:
            audit_auth(request, error)
        request.state.session_id = session_id
        request.state.secrets_to_redact = [credential.credentials, admin_token]

    def sensitive_identifier(request, value):
        return (any(secret in value for secret in request.state.secrets_to_redact)
                or re.match(r"(?i)^(bearer[.:_-]|sk[-_]|api[-_]?key[.:_-]|token[.:_-])", value) is not None
                or store.contains_session_credential(value))

    def transport_context(request):
        context = {"request_id": request.state.request_id, "call_id": None, "key": None}
        invalid = False
        for header, field in (("X-Call-ID", "call_id"), ("Idempotency-Key", "key")):
            values = request.headers.getlist(header)
            if not values:
                continue
            if (len(values) != 1 or re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", values[0]) is None
                    or sensitive_identifier(request, values[0])):
                invalid = True
            else:
                context[field] = values[0]
        return context, invalid

    def clean_raw(request, body):
        # Preserve only declared parameter names. Invalid extra-field values are never logged.
        name = request.url.path.rsplit("/", 1)[-1]
        model = m.TOOLS.get(name, (m.Empty,))[0]
        allowed = set(model.model_fields)
        def scrub(value):
            if isinstance(value, str):
                for secret in getattr(request.state, "secrets_to_redact", []):
                    value = value.replace(secret, "[REDACTED]")
                return re.sub(r"(?i)Bearer\s+\S+", "Bearer [REDACTED]", value)[:2000]
            if isinstance(value, list):
                return [scrub(item) for item in value[:30]]
            if isinstance(value, dict):
                return {key: scrub(item) if key in ("item_id", "quantity") else "[REDACTED]" for key, item in value.items()}
            if isinstance(value, float) and not math.isfinite(value):
                return "[NON_FINITE]"
            return value
        return {key: scrub(value) if key in allowed else "[REDACTED]" for key, value in body.items()} if isinstance(body, dict) else None

    def audit_protocol_failure(request, failure, body=None):
        # Error observation only: this never dispatches tools or creates a fallback execution route.
        match = re.fullmatch(r"/api/v1/sessions/([A-Za-z0-9_.:-]{1,128})/tools/([^/]+)", request.url.path)
        if not match:
            store.security_event(request.state.request_id, "UNATTRIBUTED_PROTOCOL_ERROR")
            return failure
        sid, tool_name = match.groups()
        if getattr(request.state, "session_id", None) != sid:
            authorization = request.headers.getlist("Authorization")
            parts = authorization[0].split(" ", 1) if len(authorization) == 1 else []
            credential = (HTTPAuthorizationCredentials(scheme=parts[0], credentials=parts[1])
                          if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1] else None)
            try:
                session_auth(request, sid, credential)
            except DomainError as denied:
                return denied  # Already written to the isolated security log, never the target session.
        context, _ = transport_context(request)
        raw = clean_raw(request, body) if tool_name in m.TOOLS else None
        if re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", tool_name) is None or sensitive_identifier(request, tool_name):
            tool_name = "unknown_tool"
        store.audit_failure(sid, tool_name, raw, context, failure)
        return failure

    @app.exception_handler(DomainError)
    async def domain_error(request, error):
        return JSONResponse(error.payload(request.state.request_id), status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        failure = DomainError("INVALID_REQUEST", "Request fields or transport metadata failed validation.", 422)
        if any(issue["type"] == "missing" and issue["loc"] == ("header", "Idempotency-Key") for issue in error.errors()):
            failure = DomainError("MISSING_IDEMPOTENCY_KEY", "Writes require an Idempotency-Key header.", 422)
        failure = audit_protocol_failure(request, failure, error.body)
        return JSONResponse(failure.payload(request.state.request_id), status_code=failure.status)

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        failure = DomainError("NOT_FOUND" if error.status_code == 404 else "HTTP_ERROR", "Resource or method unavailable.", error.status_code)
        failure = audit_protocol_failure(request, failure)
        return JSONResponse(failure.payload(request.state.request_id), status_code=failure.status)

    @app.exception_handler(Exception)
    async def unexpected_error(request, error):
        busy = isinstance(error, sqlite3.OperationalError) and "locked" in str(error).lower()
        failure = DomainError("DATABASE_BUSY" if busy else "INTERNAL_ERROR",
                              "Storage temporarily unavailable." if busy else "Request could not be completed.",
                              503 if busy else 500, busy)
        return JSONResponse(failure.payload(request.state.request_id), status_code=failure.status,
                            headers={"X-Request-ID": request.state.request_id, "Cache-Control": "no-store"})

    errors = {status: {"model": m.Error} for status in (401, 403, 404, 409, 422, 500, 503)}

    @app.post("/api/v1/sessions", response_model=m.CreatedSession, status_code=201,
              dependencies=[Depends(admin)], responses=errors)
    def create_session(body: m.CreateSession):
        return store.create_session(body.model_dump())

    @app.get("/api/v1/sessions/{session_id}/status", response_model=m.SessionStatus,
             dependencies=[Depends(session_auth)], responses=errors)
    def status(session_id: str):
        return store.state(session_id)["session"]

    @app.get("/api/v1/sessions/{session_id}/observation", response_model=m.Case,
             dependencies=[Depends(session_auth)], responses=errors)
    def observation(session_id: str):
        return store.state(session_id)["case"]

    def endpoint(name, request_model):
        def call(session_id: str, body, request: Request,
                 idempotency_key: str | None = Header(... if m.TOOLS[name][2] else None, alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$"),
                 call_id: str | None = Header(None, alias="X-Call-ID", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")):
            context, invalid = transport_context(request)
            if invalid:
                failure = DomainError("INVALID_REQUEST", "Transport identifiers must be unique, valid and credential-free.", 422)
                store.audit_failure(session_id, name, clean_raw(request, body.model_dump(exclude_unset=True)), context, failure)
                raise failure
            context["call_id"] = context["call_id"] or request.state.request_id
            args = body.model_dump()
            # Compare original validated parameters, before audit redaction can collapse distinct text.
            context["fingerprint"] = hashlib.sha256(dumps({"tool": name, "arguments": args}).encode()).hexdigest()
            # Free text and audit copies are redacted; transport credentials never enter facts.
            args = clean_raw(request, args)
            raw = clean_raw(request, body.model_dump(exclude_unset=True))
            return store.execute(session_id, name, args, raw, context)
        call.__annotations__["body"] = request_model
        call.__name__ = name
        return call

    for name, (request_model, response_model, _, description) in m.TOOLS.items():
        app.post(f"/api/v1/sessions/{{session_id}}/tools/{name}", response_model=response_model,
                 summary=description, operation_id=name, dependencies=[Depends(session_auth)], responses=errors)(endpoint(name, request_model))

    @app.get("/api/v1/admin/fixtures", response_model=m.FixtureCatalog,
             dependencies=[Depends(admin)], responses=errors)
    def fixtures():
        result = []
        for fixture_id in REGISTRY:
            fixture, _ = load_fixture(fixture_id)
            result.append({key: fixture[key] for key in
                           ("fixture_id", "fixture_version", "source_case_id", "fixture_source", "review_status")}
                          | {"policy_version": fixture["policy"]["policy_version"]})
        return {"fixtures": result}

    @app.get("/api/v1/admin/sessions", response_model=m.SessionPage,
             dependencies=[Depends(admin)], responses=errors)
    def sessions(tenant_id: m.Id, offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100)):
        return store.list_sessions(tenant_id, offset, limit)

    @app.get("/api/v1/admin/sessions/{session_id}/events", response_model=m.EventPage,
             dependencies=[Depends(admin)], responses=errors)
    def events(session_id: str, after_seq: int = Query(0, ge=0), limit: int | None = Query(None, ge=1, le=100)):
        return store.events(session_id, after_seq, limit)

    @app.get("/api/v1/admin/sessions/{session_id}/ledger", response_model=m.Ledger,
             dependencies=[Depends(admin)], responses=errors)
    def ledger(session_id: str):
        return store.ledger(session_id)

    @app.get("/api/v1/admin/sessions/{session_id}/evidence", response_model=m.EvidenceBundle,
             dependencies=[Depends(admin)], responses=errors)
    def evidence(session_id: str):
        return store.evidence(session_id)

    return app
