"""Standard-library HTTP transport to B. Holds only one session token; never imports sandbox/api."""
from dataclasses import dataclass
import json
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _loopback_only(base_url: str) -> str:
    parsed = urlparse(base_url)
    if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("Runner transport accepts a local loopback HTTP base_url only.")
    return base_url.rstrip("/")


@dataclass
class Transport:
    """One HTTP exchange as observed by C. outcome=response means bytes were received and parsed."""
    outcome: str  # response | timeout | connection_error | bad_response
    http_status: int | None = None
    payload: Any = None
    request_id: str | None = None
    detail: str | None = None

    @property
    def unknown(self) -> bool:
        # A write whose response never arrived, or a 5xx, does not prove whether B committed it.
        return self.outcome != "response" or (self.http_status is not None and self.http_status >= 500)


class HttpJson:
    def __init__(self, base_url: str, credential: str, timeout: float = 15.0):
        self.base_url = _loopback_only(base_url)
        self._credential = credential
        self.timeout = timeout
        self._http = build_opener(ProxyHandler({}), _NoRedirect())

    def request(self, method: str, path: str, body: Any = None, headers: dict[str, str] | None = None,
                discard_response: bool = False) -> Transport:
        all_headers = {"Authorization": "Bearer " + self._credential, "Content-Type": "application/json"}
        all_headers.update(headers or {})
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        req = Request(self.base_url + path, data=data, headers=all_headers, method=method)
        try:
            with self._http.open(req, timeout=self.timeout) as response:
                raw, status, rid = response.read(), response.status, response.headers.get("X-Request-ID")
        except HTTPError as error:
            raw, status, rid = error.read(), error.code, error.headers.get("X-Request-ID")
        except (socket.timeout, TimeoutError):
            return Transport("timeout", detail="no response within transport timeout")
        except URLError as error:
            if isinstance(error.reason, (socket.timeout, TimeoutError)):
                return Transport("timeout", detail="no response within transport timeout")
            return Transport("connection_error", detail=type(error.reason).__name__)
        except (ConnectionError, OSError) as error:
            return Transport("connection_error", detail=type(error).__name__)
        if discard_response:
            # Engineering fault injection: B finished the request but C behaves as if nothing arrived.
            return Transport("timeout", detail="engineering_fault_injection:response_discarded")
        try:
            payload = json.loads(raw)
        except ValueError:
            return Transport("bad_response", http_status=status, request_id=rid, detail="non-JSON body")
        return Transport("response", http_status=status, payload=payload, request_id=rid)


class SessionTransport:
    """Agent-side transport: the session token never leaves this object."""

    def __init__(self, base_url: str, session_id: str, session_token: str, timeout: float = 15.0):
        self.session_id = session_id
        self._http = HttpJson(base_url, session_token, timeout)
        self._prefix = f"/api/v1/sessions/{session_id}"
        self.faults: dict[str, int] = {}

    def tool(self, name: str, arguments: dict[str, Any], *, idempotency_key: str | None, call_id: str) -> Transport:
        headers = {"X-Call-ID": call_id}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        discard = self.faults.get(name, 0) > 0
        if discard:
            self.faults[name] -= 1
        return self._http.request("POST", f"{self._prefix}/tools/{name}", arguments, headers, discard_response=discard)

    def status(self) -> Transport:
        return self._http.request("GET", f"{self._prefix}/status")


class AdminTransport:
    """Orchestrator-only: creates sessions and reads evidence. Never handed to an adapter."""

    def __init__(self, base_url: str, admin_token: str, timeout: float = 15.0):
        self._http = HttpJson(base_url, admin_token, timeout)

    def create_session(self, body: dict[str, Any]) -> Transport:
        return self._http.request("POST", "/api/v1/sessions", body)

    def evidence(self, session_id: str) -> Transport:
        return self._http.request("GET", f"/api/v1/admin/sessions/{session_id}/evidence")
