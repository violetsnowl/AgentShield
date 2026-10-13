"""Validation rules for A0 insurance research contracts; stdlib only."""
from dataclasses import dataclass
from typing import Any, Mapping

class ContractError(ValueError):
    """Malformed or unsupported contract or numerical input."""


def _int(value: Any, name: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if type(value) is not int:
        raise ContractError(f"{name} must be an integer (not bool or float)")
    if value < minimum or (maximum is not None and value > maximum):
        raise ContractError(f"{name} out of permitted range")
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name} must be non-empty text")
    return value


@dataclass(frozen=True)
class ResearchContract:
    contract_version: str
    currency: str
    deductible_cents: int
    coinsurance_bp: int
    occurrence_limit_cents: int

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "ResearchContract":
        if not isinstance(raw, Mapping):
            raise ContractError("contract must be a mapping")
        keys = ("contract_version", "currency", "deductible_cents", "coinsurance_bp", "occurrence_limit_cents", "commercial_quote")
        for key in keys:
            if key not in raw:
                raise ContractError(f"missing contract field: {key}")
        if raw["commercial_quote"] is not False:
            raise ContractError("research contract must set commercial_quote=false")
        if raw["currency"] != "CNY":
            raise ContractError("A0 only supports CNY")
        return cls(
            contract_version=_text(raw["contract_version"], "contract_version"),
            currency="CNY",
            deductible_cents=_int(raw["deductible_cents"], "deductible_cents"),
            coinsurance_bp=_int(raw["coinsurance_bp"], "coinsurance_bp", maximum=10000),
            occurrence_limit_cents=_int(raw["occurrence_limit_cents"], "occurrence_limit_cents"),
        )
