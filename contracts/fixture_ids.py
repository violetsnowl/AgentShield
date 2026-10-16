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

# Public A fixtures admitted for this fixed-case integration only.  Keeping the
# IDs in source code means an HTTP caller still cannot register a file or path.
A_PUBLIC_FIXTURE_IDS = (
    "a1-w_l-01",
    "a1-p_h-03",
    "a1-p_l-05",
    "eng-a0-06",
)

# One deterministic draw from the frozen B-SCALE population.  This remains a
# source-controlled development fixture; HTTP callers cannot add tasks or paths.
BSCALE_SAMPLE_FIXTURE_IDS = (
    "bscale-r1-rr-synth-00041076",
)

FIXTURE_IDS = BASE_FIXTURE_IDS + GENERATED_FIXTURE_IDS + BSCALE_SAMPLE_FIXTURE_IDS + A_PUBLIC_FIXTURE_IDS
