"""Pure loss arithmetic (V1.1 section 9.2): O_j = max(A_j - E_j, 0); O = sum O_j; L_H = O - R."""
from typing import Any, Iterable, Mapping


class LossInputError(ValueError):
    pass


def _cents(value: Any, name: str, *, nullable: bool) -> int | None:
    if value is None and nullable:
        return None
    if type(value) is not int or value < 0:
        raise LossInputError(f"{name} must be a non-negative integer number of cents")
    return value


def compute_loss(obligations: Iterable[Mapping[str, Any]], recovery_cents: int | None) -> dict[str, Any]:
    """Per-obligation extra and underpayment never offset each other. Unknown stays None."""
    rows, unknown = [], []
    for raw in obligations:
        ref = raw["ref"]
        committed = _cents(raw["committed_cents"], f"{ref}.committed_cents", nullable=False)
        due = _cents(raw["legally_due_cents"], f"{ref}.legally_due_cents", nullable=True)
        if due is None:
            unknown.append(f"legally_due_cents:{ref}")
            # Nothing committed means no extra outflow whatever was due; the underpayment stays unknown.
            extra, under = (0 if committed == 0 else None), None
        else:
            extra, under = max(committed - due, 0), max(due - committed, 0)
        rows.append({"ref": ref, "legally_due_cents": due, "committed_cents": committed,
                     "extra_cents": extra, "underpaid_cents": under})
    if len({r["ref"] for r in rows}) != len(rows):
        raise LossInputError("obligation refs must be unique")
    extras = [r["extra_cents"] for r in rows]
    unders = [r["underpaid_cents"] for r in rows]
    total_extra = sum(extras) if None not in extras else None
    total_under = sum(unders) if None not in unders else None
    recovery = _cents(recovery_cents, "traceable_recovery_cents", nullable=True)
    if recovery is None:
        unknown.append("traceable_recovery_cents")
    if recovery is not None and total_extra is not None and recovery > total_extra:
        raise LossInputError("traceable recovery cannot exceed extra outflow (0 <= R <= O)")
    net = total_extra - recovery if total_extra is not None and recovery is not None else None
    return {"obligations": rows, "total_committed_cents": sum(r["committed_cents"] for r in rows),
            "total_extra_cents": total_extra, "total_underpaid_cents": total_under,
            "traceable_recovery_cents": recovery, "net_loss_cents": net,
            "loss_status": "verified" if net is not None else "needs_review", "unknown_parts": unknown}
