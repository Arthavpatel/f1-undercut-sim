"""
clean.py — pure transformation layer.
Takes raw FastF1 objects (from loader.py) → returns ONE canonical per-lap dataframe.
NEVER imports fastf1, never touches the network. Testable with fake dataframes.
"""
import pandas as pd


# ── STEP 1: select + rename raw lap columns into canonical names ──────────────
def _select_lap_columns(laps):
    column_map = {
        "Driver": "driver",
        "Team": "team",
        "LapNumber": "lap_number",
        "Stint": "stint",
        "Position": "position_fastf1",
        "LapStartTime": "lap_start_time",
        "LapTime": "lap_time",
        "Time": "timestamp",          
        "Compound": "compound",
        "TyreLife": "tyre_life",
        "PitInTime": "pit_in_time",
        "PitOutTime": "pit_out_time",
        "IsAccurate": "is_accurate",
        "TrackStatus" : "track_status"
    }
    return laps[list(column_map.keys())].rename(columns = column_map)

# ── STEP 2: derive computed columns ───────────────────────────────────────────
def _add_cumulative_time(df):
    df = df.copy()

    # ensure correct ordering
    df = df.sort_values(["driver", "lap_number"])

    # ensure timedelta
    df["lap_time"] = pd.to_timedelta(df["lap_time"])

    lap_time_filled = df["lap_time"].fillna(pd.Timedelta(0))

    df["cumulative_time"] = lap_time_filled.groupby(df["driver"]).cumsum()

    return df

def _add_tyre_age(df):
    df = df.copy()
    df = df.sort_values(["driver", "stint", "lap_number"])
    df["tyre_age"] = df.groupby(["driver", "stint"]).cumcount()+ 1
    return df


def _add_position_and_gaps(df):
    df = df.copy()

    # POSITION — within each lap, rank drivers by cumulative_time ascending.
    # Smallest cumulative time = covered the distance fastest = leader = P1.
    # AXIS FLIP: cumulative_time was grouped per-DRIVER across laps;
    # position is grouped per-LAP across drivers. Same column, orthogonal grouping.
    df["position"] = (
        df.groupby("lap_number")["cumulative_time"]
          .rank(method="first", ascending=True)
          .astype(int)
    )

    # GAP TO LEADER — your cumulative time minus the lap leader's (the min).
    # Your earlier logic was correct; transform expresses it without an apply.
    # Leader's own gap comes out to 0, as it should.
    df["gap_to_leader"] = (
        df.groupby("lap_number")["cumulative_time"]
          .transform(lambda t: t - t.min())
    )

    # GAP TO CAR AHEAD — the one that actually drives undercut decisions.
    # Sort each lap by position, then diff cumulative_time against the row above.
    df = df.sort_values(["lap_number", "position"])
    df["gap_to_ahead"] = df.groupby("lap_number")["cumulative_time"].diff()
    # P1 has no car ahead -> diff is NaT. Correct: the leader's gap_to_ahead is undefined.

    return df

# ── STEP 3: join track status onto each lap ───────────────────────────────────
def _merge_track_status(df, track_status):
    """
    why only return df because fastf1 already provides the track status.
    why keep it at all because in future i might want the timeline.
    """
    return df 

# ── STEP 4: flag non-representative laps ──────────────────────────────────────
def _flag_laps(df):
    df = df.copy()
    # OUTLAP = lap exiting the pits (pit_out_time recorded). "First lap of stint"
    # would wrongly flag lap 1 (the standing start) as an outlap.
    df["is_outlap"] = df["pit_out_time"].notna()
    df["is_inlap"] = df["pit_in_time"].notna()
    # SC/VSC: FastF1 per-lap track_status holds numeric CODES as strings, not
    # the letters "SC"/"VSC". 4 = Safety Car, 6/7 = Virtual Safety Car. A mid-lap
    # status change concatenates codes (e.g. "14"), so use a substring match.
    # VERIFY codes via laps["TrackStatus"].unique() on a race that HAD a safety car.
    sc_vsc_codes = ["4", "6", "7"]
    df["is_sc_vsc"] = df["track_status"].astype(str).str.contains("|".join(sc_vsc_codes), na=False)
    return df


# ── STEP 5: synthetic fill + quality flags ────────────────────────────────────
def _fill_gaps(df):
    df = df.copy()

    # Mark every row that genuinely exists BEFORE we invent any via reindex.
    # is_synthetic must mean "this row was invented", NOT "lap_time is missing"
    # (a real lap can legitimately have a missing lap_time).
    df["_real"] = True

    max_lap = int(df["lap_number"].max())

    drivers = df["driver"].unique()

    full_index = pd.MultiIndex.from_product(
        [drivers, range(1, max_lap + 1)],
        names=["driver", "lap_number"]
    )
    df = df.set_index(["driver", "lap_number"]).reindex(full_index).reset_index()

    # Invented rows have no _real marker → they are the synthetic ones.
    df["is_synthetic"] = df["_real"].isna()
    df = df.drop(columns="_real")

    if "team" in df.columns:
        df["team"] = df.groupby("driver")["team"].ffill()

    if "stint" in df.columns:
        df["stint"] = df.groupby("driver")["stint"].ffill()

    if "compound" in df.columns:
        df["compound"] = df.groupby("driver")["compound"].ffill()

    if "tyre_age" in df.columns:
        df["tyre_age"] = df.groupby(["driver", "stint"])["tyre_age"].ffill()

    return df


# ── STEP 6: validation ground truth (kept pristine) ───────────────────────────
def _attach_ground_truth(df, results):
    df = df.copy()
    results = results.copy()

    # VERIFY against results.columns.tolist(): the 3-letter driver code in
    # FastF1 results is "Abbreviation" (NOT "Driver", which does not exist here).
    # Wrong key -> KeyError, or worse, an all-NaN merge that silently breaks Phase 5.
    gt = results[["Abbreviation", "Position", "Time", "Status"]].copy()
    gt = gt.rename(columns={

        "Position": "final_position",

        "Time": "final_time",

        "Status": "final_status",

        "Abbreviation": "driver",

    })

    df = df.merge(gt, on="driver", how="left")

    return df


# ── ORCHESTRATOR: the only public function ────────────────────────────────────
def build_canonical(laps, results, track_status):
    """
    Run the pipeline in dependency order. Returns the canonical per-lap dataframe.
    """
    df = _select_lap_columns(laps)
    df = _add_cumulative_time(df)
    df = _add_tyre_age(df)
    df = _add_position_and_gaps(df)      # after cumulative_time
    df = _merge_track_status(df, track_status)
    df = _flag_laps(df)                  # after pit flags + track status
    df = _fill_gaps(df)
    df = _attach_ground_truth(df, results)
    return df