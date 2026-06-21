"""
pace.py — the pace model.
Consumes the canonical per-lap dataframe (from clean.build_canonical) and
produces lap-time predictions. Phase 2.

Structure: predicted_lap_time = base_pace[driver] + effects
  - base_pace : per-driver reference (this file, first)
  - effects   : degradation, fuel, compound, warm-up (added later as deltas)
"""
import warnings
import pandas as pd
import sys

from src.models.tyre_deg import deg_effect

def base_pace(df):
    """
    Per-driver base pace = median of each driver's clean green-flag laps.

    Only drivers with at least one clean lap receive a pace estimate.

    Drivers who have real laps but no clean laps are omitted from the
    returned Series and trigger a warning so the edge case is visible.
    """

    real = df[~df["is_synthetic"]]

    clean = real[
        ~real["is_outlap"]
        & ~real["is_inlap"]
        & ~real["is_sc_vsc"]
        & real["is_accurate"]
    ]

    result = clean.groupby("driver")["lap_time"].median()

    drivers_real = set(real["driver"].unique())
    drivers_with_pace = set(result.index)

    missing = drivers_real - drivers_with_pace

    if missing:
        warnings.warn(
            f"Drivers with real laps but no clean laps: {sorted(missing)}",
            RuntimeWarning,
        )

    return result

def predicted_lap_time(
    driver,
    lap_number,
    tyre_age,
    compound,
    base_pace,
    fuel_effect_func,
    deg_rates,
    reference_age
):

    base = base_pace[driver].total_seconds()

    # --- fuel correction (already reference-frame aligned) ---
    fuel = fuel_effect_func(lap_number)

    # --- tyre degradation correction ---
    deg = deg_effect(
        tyre_age,
        compound,
        deg_rates,
        reference_age
    )

    # --- final assembly ---
    return base + fuel + deg