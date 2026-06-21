"""
fuel.py — fuel-burn correction for the pace model.
Cars get lighter as fuel burns off, so laps get faster through the race.
This module expresses that as a correction RELATIVE TO the fuel load that
base_pace already represents (the median clean lap ≈ mid-race fuel), so the
two never double-count.

predicted_lap_time = base_pace[driver] + fuel_effect(lap) + (other effects)
"""

# ── Constants (ESTIMATES — flag as such; not Hungary-measured) ────────────────
# Source/justification matters in interviews: say where each came from.
START_FUEL_KG = 110.0        # 2019 max race allowance; likely an over-estimate
                             # (low-fuel circuits start below max). Upper bound.
END_FUEL_KG = 0.0            # assume ~empty at flag (really ~1kg FIA sample) —
                             # slightly overstates burn, within tolerance.
SECONDS_PER_KG = 0.035       # general F1 estimate (~0.03–0.04). Circuit-specific
                             # in reality; not measured for Hungary. ESTIMATE.


def fuel_burn_per_lap(total_laps):
    """
    kg of fuel burned each lap = (start - end) / total_laps.
    Assumes linear burn (reasonable simplification).
    YOU WRITE: the one-line calculation.
    """
    fuel_burn = START_FUEL_KG / total_laps
    return fuel_burn


def fuel_remaining(lap_number, total_laps):
    burn = fuel_burn_per_lap(total_laps)
    fuel_rem = START_FUEL_KG - ((lap_number - 1) * burn)
    return fuel_rem


def fuel_effect(lap_number, total_laps, reference_lap=None):
    if reference_lap is None:
        reference_lap = total_laps / 2

    fuel_at_lap = fuel_remaining(lap_number, total_laps)
    fuel_at_reference = fuel_remaining(reference_lap, total_laps)

    return (fuel_at_lap - fuel_at_reference) * SECONDS_PER_KG

def make_fuel_effect(total_laps):
    def fuel_effect(lap_number):
        fuel_at_lap = fuel_remaining(lap_number, total_laps)
        fuel_at_reference = fuel_remaining(total_laps / 2, total_laps)
        return (fuel_at_lap - fuel_at_reference) * SECONDS_PER_KG
    return fuel_effect