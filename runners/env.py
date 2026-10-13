"""Read the few runner settings C owns from the process environment or the git-ignored project .env."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = ("DEEPSEEK_API_KEY", "C_ENABLE_PAID_RUNS", "C_MAX_COST_CNY")


def load_runner_env(path: Path | None = None) -> dict[str, str]:
    values: dict[str, str] = {}
    env_file = path or ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key in ALLOWED and value:
                values[key] = value
    for key in ALLOWED:
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def paid_authorization(values: dict[str, str]) -> tuple[bool, float | None, str]:
    """Paid calls need an explicit opt-in, a positive CNY cap and a key. Default is off."""
    if values.get("C_ENABLE_PAID_RUNS", "false").lower() != "true":
        return False, None, "C_ENABLE_PAID_RUNS is not true"
    try:
        cap = float(values.get("C_MAX_COST_CNY", "0"))
    except ValueError:
        return False, None, "C_MAX_COST_CNY is not a number"
    if cap <= 0:
        return False, None, "C_MAX_COST_CNY must be positive"
    if not values.get("DEEPSEEK_API_KEY"):
        return False, cap, "DEEPSEEK_API_KEY missing"
    return True, cap, "authorized"
