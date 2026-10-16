"""Classify whether a failed episode may be repeated. This does not launch anything.

A repeated episode replaces an infrastructure failure. It is not a new business
sample and it is not a way to keep the better model outcome.
"""
from typing import Any


def classify_rerun(run_status: str, stop_reason: str | None, *, already_rerun: bool = False,
                   purpose: str = "improve_score") -> dict[str, Any]:
    if purpose != "infrastructure_recovery":
        return {"decision": "forbidden_cherry_pick", "counts_as_new_sample": False, "new_episode": False}
    reason = stop_reason or ""
    eligible = run_status in {"infra_error", "not_started"} or "transport_unknown" in reason
    if run_status == "completed" or not eligible or already_rerun:
        return {"decision": "record_only", "counts_as_new_sample": False, "new_episode": False}
    return {"decision": "infra_rerun_eligible", "counts_as_new_sample": False, "new_episode": True}
