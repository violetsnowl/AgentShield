"""SQLite is the transaction authority; JSON exports are derived, never a second ledger."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
from uuid import uuid4

from contracts.models import EvidenceBundle, Snapshot, TOOLS, ToolEvent
from sandbox.fixture import FixtureError, snapshot


def now():
    return datetime.now(timezone.utc).isoformat()


def uid(prefix):
    return f"{prefix}-{uuid4().hex}"


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class DomainError(Exception):
    def __init__(self, code, message, status=409, retryable=False):
        super().__init__(message)
        self.code, self.message, self.status, self.retryable = code, message, status, retryable

    def payload(self, request_id):
        return {"code": self.code, "message": self.message, "retryable": self.retryable, "request_id": request_id}


class Store:
    def __init__(self, path):
        self.path = Path(path)

    def connect(self):
        con = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        return con

    @contextmanager
    def transaction(self, write=False):
        con = self.connect()
        try:
            con.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = self.connect()
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA synchronous=FULL")
            con.executescript((Path(__file__).parents[1] / "migrations/001_initial.sql").read_text())
            con.executescript((Path(__file__).parents[1] / "migrations/002_human_reviews.sql").read_text())
            con.executescript((Path(__file__).parents[1] / "migrations/003_session_cases.sql").read_text())
        finally:
            con.close()

    def create_session(self, args):
        sid, token = uid("session"), secrets.token_urlsafe(32)
        try:
            state, case_context = snapshot(sid, args)
        except FixtureError:
            raise DomainError("INVALID_FIXTURE", "Registered development fixture is invalid or unavailable.", 422) from None
        state = Snapshot.model_validate(state).model_dump()
        with self.transaction(True) as con:
            con.execute("INSERT INTO sessions VALUES (?,?,?,?)",
                        (sid, hashlib.sha256(token.encode()).hexdigest(), dumps(state), dumps(state)))
            self._insert_case_context(con, sid, case_context)
        return {"session": state["session"], "session_token": token, "case_context": case_context}

    def _insert_case_context(self, con, sid, case_context):
        con.execute("INSERT INTO session_cases VALUES (?,?)", (sid, dumps(case_context)))

    def _case_context(self, con, sid):
        row = con.execute("SELECT payload FROM session_cases WHERE session_id=?", (sid,)).fetchone()
        return json.loads(row[0]) if row else None

    def authenticate(self, sid, token):
        with self.transaction() as con:
            row = con.execute("SELECT session_id FROM sessions WHERE token_hash=?",
                              (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if row is None:
            raise DomainError("UNAUTHORIZED", "A valid session credential is required.", 401)
        if row["session_id"] != sid:
            raise DomainError("FORBIDDEN", "Session credential does not authorize this resource.", 403)

    def security_event(self, request_id, code):
        with self.transaction(True) as con:
            con.execute("INSERT INTO security_events VALUES (?,?,?,?)", (uid("security"), now(), request_id, code))

    def contains_session_credential(self, value):
        # Locally generated session tokens are 43 URL-safe characters; also check exact values.
        candidates = {value} | {value[i:i + 43] for i in range(max(0, len(value) - 42))}
        hashes = [hashlib.sha256(candidate.encode()).hexdigest() for candidate in candidates]
        with self.transaction() as con:
            return con.execute("SELECT 1 FROM sessions WHERE token_hash IN (" + ",".join("?" for _ in hashes) + ") LIMIT 1", hashes).fetchone() is not None

    def _state(self, con, sid):
        row = con.execute("SELECT state_json FROM sessions WHERE session_id=?", (sid,)).fetchone()
        if row is None:
            raise DomainError("NOT_FOUND", "Session not found.", 404)
        return json.loads(row[0])

    def state(self, sid):
        with self.transaction() as con:
            return self._state(con, sid)

    def _order(self, state, oid):
        for order in state["orders"]:
            if order["order_id"] == oid:
                if order["tenant_id"] != state["session"]["tenant_id"] or order["customer_id"] != state["case"]["customer_id"]:
                    break
                return order
        raise DomainError("OBJECT_FORBIDDEN", "Object is outside this session's authorized scope.", 403)

    def _scope(self, state, name, args):
        order, message = None, None
        if "order_id" in args:
            order = self._order(state, args["order_id"])
        if name == "submit_refund":
            allowed_items = {item["item_id"] for item in order["items"]}
            if any(item["item_id"] not in allowed_items for item in args["items"]):
                raise DomainError("OBJECT_FORBIDDEN", "Item does not belong to the authorized order.", 403)
            message = next((message for message in state["case"]["messages"]
                            if message["message_id"] == args["confirmation_message_id"]), None)
            if message is None or message["customer_id"] != order["customer_id"]:
                raise DomainError("OBJECT_FORBIDDEN", "Message is outside this session's authorized scope.", 403)
            if message["confirmation"] is None or message["confirmation"]["order_id"] != order["order_id"]:
                raise DomainError("CONFIRMATION_SCOPE", "Confirmation does not authorize this order.")
        if name == "submit_human_review":
            allowed_messages = {message["message_id"] for message in state["case"]["messages"]
                                if message["customer_id"] == state["case"]["customer_id"]}
            if any(mid not in allowed_messages for mid in args["evidence_message_ids"]):
                raise DomainError("OBJECT_FORBIDDEN", "Evidence message is outside this session's authorized scope.", 403)
            if len(set(args["evidence_message_ids"])) != len(args["evidence_message_ids"]):
                raise DomainError("DUPLICATE_EVIDENCE", "Each evidence message may appear only once.")
        return order, message

    def _event(self, con, state, name, args, raw, context, status, before, result=None, error=None):
        session = state["session"]
        seq = con.execute("SELECT COALESCE(MAX(seq),0)+1 FROM events WHERE session_id=?",
                          (session["session_id"],)).fetchone()[0]
        transaction = result if name == "submit_refund" and status in ("succeeded", "replayed") else None
        case_context = self._case_context(con, session["session_id"])
        business_time = case_context["canonical_initial"]["business_time"] if case_context else "2026-10-11T12:00:00+08:00"
        event = {"event_id": uid("event"), "request_id": context["request_id"],
                 **{key: session[key] for key in ("experiment_id", "episode_id", "case_id", "session_id", "config_id")},
                 "seq": seq, "recorded_at": now(), "business_time": business_time,
                 "tool_name": name, "call_id": context.get("call_id"), "raw_arguments": raw,
                 "validated_arguments": args, "idempotency_key": context.get("key"), "status": status,
                 "session_version_before": before, "session_version_after": session["version"],
                 "order_version_before": transaction["order_version_before"] if transaction and status == "succeeded" else None,
                 "order_version_after": transaction["order_version_after"] if transaction and status == "succeeded" else None,
                 "transaction_id": transaction["transaction_id"] if transaction else None,
                 "ticket_id": result["ticket_id"] if name == "submit_human_review" and status in ("succeeded", "replayed") else None,
                 "committed_amount_cents": transaction["amount_cents"] if transaction and status == "succeeded" else 0,
                 "result": result, "error": error, "client_receipt": "unknown", "sources": session["sources"]}
        ToolEvent.model_validate(event)
        con.execute("INSERT INTO events VALUES (?,?,?,?)", (session["session_id"], seq, event["event_id"], dumps(event)))

    def audit_failure(self, sid, name, raw, context, error, args=None):
        with self.transaction(True) as con:
            state = self._state(con, sid)
            self._event(con, state, name, args, raw, context, "error" if error.status >= 500 else "rejected",
                        state["session"]["version"], error=error.payload(context["request_id"]))

    def _rows(self, con, table, sid):
        # table is selected by internal callers only, never transport input.
        if table not in ("refunds", "ledger", "events", "human_reviews"):
            raise ValueError("Unknown fact table")
        ordering = "seq" if table == "events" else "rowid"
        return [json.loads(row[0]) for row in con.execute(
            f"SELECT payload FROM {table} WHERE session_id=? ORDER BY {ordering}", (sid,))]

    def _history(self, con, sid, args):
        refunds = [row for row in self._rows(con, "refunds", sid) if row["order_id"] == args["order_id"]]
        key = args.get("idempotency_key")
        transaction = next((row for row in refunds if row["idempotency_key"] == key), None) if key else None
        return {"order_id": args["order_id"], "refunds": refunds, "requested_key": key,
                "request_status": "committed" if transaction else "not_found" if key else "not_requested",
                "transaction_id": transaction["transaction_id"] if transaction else None}

    def _insert_ledger(self, con, entry):
        con.execute("INSERT INTO ledger VALUES (?,?,?,?)",
                    (entry["entry_id"], entry["transaction_id"], entry["session_id"], dumps(entry)))

    def _human_review(self, con, state, args, context):
        session = state["session"]
        before = session["version"]
        session["version"] += 1
        ticket = {"ticket_id": uid("review"), "session_id": session["session_id"], "case_id": session["case_id"],
                  "category": args["category"], "missing_facts": args["missing_facts"],
                  "evidence_message_ids": args["evidence_message_ids"], "status": "open", "created_at": now(),
                  "idempotency_key": context["key"], "call_id": context["call_id"],
                  "session_version_before": before, "session_version_after": session["version"], "sources": session["sources"]}
        con.execute("INSERT INTO human_reviews VALUES (?,?,?)", (ticket["ticket_id"], session["session_id"], dumps(ticket)))
        return ticket

    def _refund(self, con, state, args, order, message, context):
        seen = set()
        scopes = {item["item_id"]: item["quantity"] for item in message["confirmation"]["items"]}
        committed = []
        for request_line in args["items"]:
            iid, quantity = request_line["item_id"], request_line["quantity"]
            if iid in seen:
                raise DomainError("DUPLICATE_ITEM", "Each item may appear only once.")
            seen.add(iid)
            line = next(item for item in order["items"] if item["item_id"] == iid)
            if not line["eligible"]:
                raise DomainError("NOT_ELIGIBLE", "Item is not currently eligible for refund.")
            cumulative = line["refunded_quantity"] + quantity
            if cumulative > line["quantity"]:
                raise DomainError("QUANTITY_LIMIT", "Requested quantity exceeds remaining purchased quantity.")
            if cumulative > scopes.get(iid, 0):
                raise DomainError("CONFIRMATION_SCOPE", "Requested cumulative quantity exceeds confirmation scope.")
            target = line["allocated_paid_cents"] * cumulative // line["quantity"]
            amount = target - line["refunded_cents"]
            line.update(refunded_quantity=cumulative, refundable_quantity=line["quantity"] - cumulative,
                        refunded_cents=target)
            committed.append({"item_id": iid, "quantity": quantity, "amount_cents": amount})
        amount = sum(line["amount_cents"] for line in committed)
        if amount > order["remaining_cents"] or amount > state["merchant_balance_cents"]:
            raise DomainError("AMOUNT_LIMIT", "Refund would exceed remaining paid balance.")
        version = order["version"]
        order["version"] += 1
        order["refunded_cents"] += amount
        order["remaining_cents"] -= amount
        order["status"] = "refunded" if all(i["refunded_quantity"] == i["quantity"] for i in order["items"]) else "partially_refunded"
        state["session"]["version"] += 1
        state["merchant_balance_cents"] -= amount
        state["customer_balance_cents"] += amount
        refund = {"transaction_id": uid("refund"), "session_id": state["session"]["session_id"],
                  "order_id": order["order_id"], "items": committed, "amount_cents": amount,
                  "channel": order["original_channel"], "confirmation_message_id": args["confirmation_message_id"],
                  "idempotency_key": context["key"], "call_id": context["call_id"], "committed_at": now(),
                  "order_version_before": version, "order_version_after": order["version"],
                  "session_version_after": state["session"]["version"], "status": "committed"}
        con.execute("INSERT INTO refunds VALUES (?,?,?)", (refund["transaction_id"], refund["session_id"], dumps(refund)))
        entry = {"entry_id": uid("ledger"), "transaction_id": refund["transaction_id"], "session_id": refund["session_id"],
                 "order_id": refund["order_id"], "merchant_delta_cents": -amount, "customer_delta_cents": amount,
                 "merchant_balance_cents": state["merchant_balance_cents"], "customer_balance_cents": state["customer_balance_cents"]}
        self._insert_ledger(con, entry)
        return refund

    def execute(self, sid, name, args, raw, context):
        try:
            with self.transaction(True) as con:
                state = self._state(con, sid)
                before = state["session"]["version"]
                order, message = self._scope(state, name, args)
                write = TOOLS[name][2]
                fingerprint = context.get("fingerprint") or hashlib.sha256(dumps({"tool": name, "arguments": args}).encode()).hexdigest()
                if write:
                    if not context.get("key"):
                        raise DomainError("MISSING_IDEMPOTENCY_KEY", "Writes require an Idempotency-Key header.", 422)
                    previous = con.execute("SELECT fingerprint,result_json FROM requests WHERE session_id=? AND idempotency_key=?",
                                           (sid, context["key"])).fetchone()
                    if previous:
                        if previous["fingerprint"] != fingerprint:
                            raise DomainError("IDEMPOTENCY_CONFLICT", "Key has already committed different arguments or tool.")
                        result = json.loads(previous["result_json"])
                        self._event(con, state, name, args, raw, context, "replayed", before, result)
                        return result
                    if state["session"]["status"] != "active":
                        raise DomainError("SESSION_FINISHED", "New writes are not allowed after finish_case.")
                    version = order["version"] if name == "submit_refund" else before
                    if args["expected_version"] != version:
                        raise DomainError("STALE_STATE", "Expected version does not match current state.")
                if name == "get_case":
                    result = state["case"]
                elif name == "get_order":
                    result = order
                elif name == "get_business_policy":
                    result = state["policy"]
                elif name == "get_refund_history":
                    result = self._history(con, sid, args)
                elif name == "submit_refund":
                    result = self._refund(con, state, args, order, message, context)
                elif name == "submit_human_review":
                    result = self._human_review(con, state, args, context)
                elif name == "finish_case":
                    state["session"].update(status="finished", outcome=args["outcome"], explanation=args["explanation"], version=before + 1)
                    result = state["session"]
                else:
                    raise DomainError("NOT_FOUND", "Tool is not implemented.", 404)
                result = TOOLS[name][1].model_validate(result).model_dump()
                if write:
                    Snapshot.model_validate(state)
                    con.execute("UPDATE sessions SET state_json=? WHERE session_id=?", (dumps(state), sid))
                    con.execute("INSERT INTO requests VALUES (?,?,?,?)", (sid, context["key"], fingerprint, dumps(result)))
                self._event(con, state, name, args, raw, context, "succeeded", before, result)
                return result
        except DomainError as error:
            self.audit_failure(sid, name, raw, context, error, args)
            raise
        except Exception as exc:
            busy = isinstance(exc, sqlite3.OperationalError) and "locked" in str(exc).lower()
            error = DomainError("DATABASE_BUSY" if busy else "INTERNAL_ERROR", "Storage temporarily unavailable." if busy else "Request failed without a new committed transaction.", 503 if busy else 500, busy)
            try:
                self.audit_failure(sid, name, raw, context, error, args)
            except sqlite3.Error:
                # Storage itself unavailable: do not invent a durable audit record.
                pass
            raise error from None

    def evidence(self, sid):
        with self.transaction() as con:
            final = self._state(con, sid)
            initial = json.loads(con.execute("SELECT initial_json FROM sessions WHERE session_id=?", (sid,)).fetchone()[0])
            case_context = self._case_context(con, sid)
            bundle = {"schema_version": 3, "exported_at": now(), "initial_snapshot": initial,
                      "case_context": case_context, "case_context_status": "recorded" if case_context else "legacy_unavailable",
                      "final_snapshot": final, "refunds": self._rows(con, "refunds", sid),
                      "ledger": self._rows(con, "ledger", sid), "events": self._rows(con, "events", sid),
                      "human_reviews": self._rows(con, "human_reviews", sid),
                      "policy": final["policy"], "sources": final["session"]["sources"]}
            return EvidenceBundle.model_validate(bundle).model_dump()

    def list_sessions(self, tenant_id, offset, limit):
        with self.transaction() as con:
            rows = con.execute(
                "SELECT state_json FROM sessions WHERE json_extract(state_json, '$.session.tenant_id')=? "
                "ORDER BY rowid DESC LIMIT ? OFFSET ?", (tenant_id, limit + 1, offset)).fetchall()
            return {"sessions": [json.loads(row[0])["session"] for row in rows[:limit]],
                    "next_offset": offset + limit if len(rows) > limit else None}

    def events(self, sid, after_seq, limit=None):
        with self.transaction() as con:
            self._state(con, sid)
            events = [json.loads(row[0]) for row in con.execute(
                "SELECT payload FROM events WHERE session_id=? AND seq>? ORDER BY seq LIMIT ?",
                (sid, after_seq, limit if limit is not None else -1))]
            return {"events": events, "last_seq": events[-1]["seq"] if events else after_seq}

    def ledger(self, sid):
        with self.transaction() as con:
            self._state(con, sid)
            return {"entries": self._rows(con, "ledger", sid)}
