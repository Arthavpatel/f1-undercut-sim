"""
tyre_deg.py — tyre degradation model (fuel-decoupled)

Goal:
- Extract PURE tyre degradation rates from lap data
- Remove fuel influence using an external fuel-correction function
- Keep degradation as a per-compound linear rate (s / lap of tyre age)
- Apply reference framing ONLY at the effect stage (mirrors fuel_effect)

Pipeline:
    raw lap time
        → fuel correction (function injected from fuel.py)
        → degradation slope estimation (linear fit over all stint laps)
        → deg_effect applied in the simulator, relative to a reference age

This keeps fuel and tyre wear cleanly separated — no double-counting.

NOTE on dependency direction:
    This module NEVER imports fuel internals. It RECEIVES a fuel-correction
    function (lap_number -> seconds) as a parameter. The function is built in
    fuel.py via make_fuel_effect(total_laps). That is the whole point of the
    injection: tyre_deg stays ignorant of how fuel is computed.

NOTE on column names:
    These functions consume THIS project's canonical schema (from
    clean.build_canonical): lap_time (timedelta), lap_number, stint, compound,
    tyre_age. They do NOT use the old repo's LapTimeSeconds / LapNumber / Stint.
"""

import numpy as np


# ─────────────────────────────────────────────────────────────
# Degradation extraction (PURE SIGNAL)
# ─────────────────────────────────────────────────────────────
def calculate_degradation(compound_laps, compound_name, fallback, fuel_effect_func):
    """
    Average degradation rate for one compound, in seconds per lap of tyre age.

    Method:
      - fuel-correct each lap time first (remove fuel influence)
      - fit a linear slope over ALL laps in each stint (robust to single bad laps)
      - average the slopes across stints

    Args:
      compound_laps   : clean canonical laps for ONE compound (df slice)
      compound_name   : str, for the "not used" message
      fallback        : rate to return if the compound has no usable stints
      fuel_effect_func: function lap_number -> fuel correction in SECONDS
                        (build with fuel.make_fuel_effect(total_laps))

    Returns: float, pure tyre-wear rate (s / lap).
    """
    degradations = []

    if compound_laps.empty:
        print(f"No {compound_name} tyres were used in this Grand Prix")
        return fallback

    for (driver, stint_num), stint in compound_laps.groupby(["driver", "stint"]):
        stint = stint.sort_values("lap_number").copy()

        MIN_LAPS_FOR_SLOPE = 6 
        if len(stint) < MIN_LAPS_FOR_SLOPE:
            continue

        # lap_time is a timedelta in the canonical schema → convert to seconds
        lap_time_s = stint["lap_time"].dt.total_seconds()

        # ── Fuel correction (critical decoupling step) ──
        # subtract the fuel cost so the remaining slope is PURE degradation
        fuel_corr_time = lap_time_s - stint["lap_number"].map(fuel_effect_func)

        x = stint["lap_number"].to_numpy(dtype=float)
        y = fuel_corr_time.to_numpy(dtype=float)

        # guard: a fit needs variation in x; skip degenerate stints
        if np.all(x == x[0]):
            continue

        # ── Linear regression slope over ALL laps ──
        slope = np.polyfit(x, y, 1)[0]
        print(f"{compound_name} | {driver} stint {stint_num} | n={len(stint)} | slope={slope:.4f}")  # ADD THIS
        degradations.append(slope)

    return float(np.mean(degradations)) if degradations else fallback


# ─────────────────────────────────────────────────────────────
# Degradation application (REFERENCE FRAME)
# ─────────────────────────────────────────────────────────────
def deg_effect(tyre_age, compound, deg_rates, reference_age):
    """
    Lap-time correction (seconds) from tyre wear, relative to a reference age.

        deg_effect = rate[compound] * (tyre_age - reference_age[compound])

    - reference_age is per-compound (the typical tyre age that base_pace's
      median clean lap represents) → zero correction at the operating point.
    - Mirrors fuel_effect's reference-frame design (no double-counting).
    """
    return deg_rates[compound] * (tyre_age - reference_age[compound])


# ─────────────────────────────────────────────────────────────
# Reference age builder
# ─────────────────────────────────────────────────────────────
def compute_reference_age(clean_laps):
    """
    Per-compound reference TYRE AGE = median tyre_age across that compound's
    clean laps.

    IMPORTANT: this uses tyre_age (laps on the current set, resets each stint),
    NOT lap_number. deg_effect subtracts this from a tyre_age, so the reference
    must be in tyre-age units or the correction is nonsense.
    """
    reference_age = {}
    for compound, grp in clean_laps.groupby("compound"):
        if grp.empty:
            continue
        reference_age[compound] = grp["tyre_age"].median()
    return reference_age


# ─────────────────────────────────────────────────────────────
# Default fallback degradation rates (s / lap)
# soft wears fastest, hard slowest — used only if a compound is unusable.
# ─────────────────────────────────────────────────────────────
default_soft_deg = 0.10
default_medium_deg = 0.05
default_hard_deg = 0.02