"""Source-controlled fixture allowlist. HTTP callers cannot add entries."""

BASE_FIXTURE_IDS = ("dev-refund-v1", "dev-refund-v2")
_CATEGORIES = ("whole-low", "whole-high", "partial-low", "partial-high")
_STRESS = ("injection", "conflict", "maximum", "ineligible")

L0_FIXTURE_IDS = tuple(
    f"bcp2-l0-{category}-{index:02d}"
    for category in _CATEGORIES
    for index in range(1, 3)
) + tuple(f"bcp2-l0-stress-{name}" for name in _STRESS)

L1_FIXTURE_IDS = tuple(
    f"bcp2-l1-{category}-{index:02d}"
    for category in _CATEGORIES
    for index in range(1, 7)
) + tuple(f"bcp2-l1-stress-{name}" for name in _STRESS)

GENERATED_FIXTURE_IDS = L0_FIXTURE_IDS + L1_FIXTURE_IDS
FIXTURE_IDS = BASE_FIXTURE_IDS + GENERATED_FIXTURE_IDS
