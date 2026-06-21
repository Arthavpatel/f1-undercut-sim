"""
Unit tests for clean.py — fully OFFLINE (no FastF1, no network).
This is the payoff of keeping clean.py pure: every transform is testable with
small fake dataframes that we fully control, so each test pins down a specific
behaviour (and the bugs we fixed can never silently come back).

Run:  python src/tests/test_clean.py      (or: pytest src/tests/test_clean.py)
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root

from src.data_layer.clean import (
    _select_lap_columns,
    _add_cumulative_time,
    _add_tyre_age,
    _add_position_and_gaps,
    _flag_laps,
    _fill_gaps,
    _attach_ground_truth,
    build_canonical,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures: minimal fake frames shaped like what FastF1 / earlier steps produce.
# ──────────────────────────────────────────────────────────────────────────────
def _fake_raw_laps():
    """Shaped like loader.get_laps output (raw FastF1 column names)."""
    return pd.DataFrame({
        "Driver":       ["HAM", "HAM", "VER", "VER"],
        "Team":         ["Mercedes", "Mercedes", "Red Bull", "Red Bull"],
        "LapNumber":    [1, 2, 1, 2],
        "Stint":        [1, 1, 1, 1],
        "Position":     [1, 1, 2, 2],
        "LapStartTime": pd.to_timedelta(["0:00:00", "0:01:20", "0:00:01", "0:01:22"]),
        "LapTime":      pd.to_timedelta([pd.NaT, "0:01:20", pd.NaT, "0:01:22"]),
        "Time":         pd.to_timedelta(["0:01:20", "0:02:40", "0:01:22", "0:02:44"]),
        "Compound":     ["MEDIUM", "MEDIUM", "MEDIUM", "MEDIUM"],
        "TyreLife":     [1, 2, 1, 2],
        "PitInTime":    [pd.NaT, pd.NaT, pd.NaT, pd.NaT],
        "PitOutTime":   [pd.NaT, pd.NaT, pd.NaT, pd.NaT],
        "IsAccurate":   [True, True, True, True],
        "TrackStatus":  ["1", "1", "1", "1"],
        "SpeedST":      [310, 311, 308, 309],   # extra col with no consumer → must be dropped
    })


def _fake_results():
    """Shaped like loader.get_results — note the 3-letter code is 'Abbreviation'."""
    return pd.DataFrame({
        "Abbreviation":   ["HAM", "VER"],
        "Position":       [1, 2],
        "Time":           pd.to_timedelta(["1:30:00", "1:30:02"]),
        "Status":         ["Finished", "Finished"],
        "FullName":       ["Lewis Hamilton", "Max Verstappen"],  # extra, ignored
    })


# ──────────────────────────────────────────────────────────────────────────────
# STEP 1 — select + rename
# ──────────────────────────────────────────────────────────────────────────────
def test_select_renames_and_drops():
    out = _select_lap_columns(_fake_raw_laps())
    assert "driver" in out.columns          # renamed to canonical
    assert "lap_time" in out.columns
    assert "Driver" not in out.columns       # raw name gone (renamed, not duplicated)
    assert "SpeedST" not in out.columns      # no consumer → dropped
    assert len(out) == 4                      # no rows lost


# ──────────────────────────────────────────────────────────────────────────────
# STEP 2 — cumulative time  (pins the NaT-on-lap-1 fix + per-driver grouping)
# ──────────────────────────────────────────────────────────────────────────────
def test_cumulative_time_handles_nat_and_groups():
    raw = pd.DataFrame({
        "driver":     ["HAM", "HAM", "HAM", "VER", "VER", "VER"],
        "lap_number": [1, 2, 3, 1, 2, 3],
        "lap_time":   pd.to_timedelta(
            [pd.NaT, "0:01:20", "0:01:21",   # HAM lap 1 missing
             pd.NaT, "0:01:22", "0:01:23"]   # VER lap 1 missing
        ),
    })
    out = _add_cumulative_time(raw)

    # NaT must NOT propagate into cumulative_time
    assert out["cumulative_time"].isna().sum() == 0

    # per-driver: HAM lap3 = 0 + 80 + 81 = 161s  (proves VER's laps excluded)
    ham3 = out[(out["driver"] == "HAM") & (out["lap_number"] == 3)]
    assert ham3["cumulative_time"].iloc[0] == pd.Timedelta(seconds=161)

    # monotonic within a driver
    ham = out[out["driver"] == "HAM"].sort_values("lap_number")
    assert ham["cumulative_time"].is_monotonic_increasing


# ──────────────────────────────────────────────────────────────────────────────
# tyre age  (resets per stint, counts from 1)
# ──────────────────────────────────────────────────────────────────────────────
def test_tyre_age_resets_per_stint():
    raw = pd.DataFrame({
        "driver":     ["HAM", "HAM", "HAM", "HAM"],
        "stint":      [1, 1, 2, 2],          # pit between lap 2 and 3
        "lap_number": [1, 2, 3, 4],
    })
    out = _add_tyre_age(raw).sort_values("lap_number")
    assert list(out["tyre_age"]) == [1, 2, 1, 2]   # resets at the new stint


# ──────────────────────────────────────────────────────────────────────────────
# STEP 2 — position & gaps  (axis flip: rank per LAP)
# ──────────────────────────────────────────────────────────────────────────────
def test_position_ranks_per_lap():
    raw = pd.DataFrame({
        "driver":          ["HAM", "VER", "HAM", "VER"],
        "lap_number":      [1, 1, 2, 2],
        "cumulative_time": pd.to_timedelta(["0:01:20", "0:01:22",   # lap1: HAM ahead
                                            "0:02:45", "0:02:44"]),  # lap2: VER ahead
    })
    out = _add_position_and_gaps(raw)

    lap1 = out[out["lap_number"] == 1].set_index("driver")
    lap2 = out[out["lap_number"] == 2].set_index("driver")
    assert lap1.loc["HAM", "position"] == 1      # smaller cumulative time = P1
    assert lap2.loc["VER", "position"] == 1      # lead changed → per-lap ranking works

    # leader's gap_to_leader is exactly 0
    assert lap1.loc["HAM", "gap_to_leader"] == pd.Timedelta(0)
    # leader has no car ahead → gap_to_ahead is NaT
    assert pd.isna(lap1.loc["HAM", "gap_to_ahead"])


# ──────────────────────────────────────────────────────────────────────────────
# STEP 4 — flags  (pins the is_outlap + is_sc_vsc fixes)
# ──────────────────────────────────────────────────────────────────────────────
def test_flags():
    raw = pd.DataFrame({
        "driver":       ["HAM", "HAM", "HAM"],
        "stint":        [1, 1, 2],
        "lap_number":   [1, 2, 3],
        # lap 3 is the out-lap (pit_out_time set); lap 2 is the in-lap (pit_in_time set)
        "pit_in_time":  [pd.NaT, pd.to_timedelta("1:00:00"), pd.NaT],
        "pit_out_time": [pd.NaT, pd.NaT, pd.to_timedelta("1:00:25")],
        "track_status": ["1", "4", "1"],   # lap 2 had a Safety Car (code 4)
    })
    out = _flag_laps(raw)

    # lap 1 (standing start) must NOT be flagged as an outlap
    assert out.loc[out["lap_number"] == 1, "is_outlap"].iloc[0] == False
    # lap 3 (exited pits) IS the outlap
    assert out.loc[out["lap_number"] == 3, "is_outlap"].iloc[0] == True
    # lap 2 IS the inlap
    assert out.loc[out["lap_number"] == 2, "is_inlap"].iloc[0] == True
    # SC detected on lap 2 via numeric code, not the letters "SC"
    assert out.loc[out["lap_number"] == 2, "is_sc_vsc"].iloc[0] == True
    assert out.loc[out["lap_number"] == 1, "is_sc_vsc"].iloc[0] == False


# ──────────────────────────────────────────────────────────────────────────────
# STEP 5 — fill  (is_synthetic means "invented row", not "missing lap_time")
# ──────────────────────────────────────────────────────────────────────────────
def test_fill_marks_only_invented_rows():
    # HAM ran laps 1-3; VER only ran lap 1 (retired). Max lap = 3.
    raw = pd.DataFrame({
        "driver":     ["HAM", "HAM", "HAM", "VER"],
        "lap_number": [1, 2, 3, 1],
        "team":       ["Mercedes"] * 3 + ["Red Bull"],
        "stint":      [1, 1, 1, 1],
        "compound":   ["MEDIUM"] * 4,
        "tyre_age":   [1, 2, 3, 1],
        "lap_time":   pd.to_timedelta(["0:01:20", "0:01:20", "0:01:20", "0:01:22"]),
    })
    out = _fill_gaps(raw)

    # VER laps 2 & 3 were invented → synthetic; all real rows are not
    ver = out[out["driver"] == "VER"].set_index("lap_number")
    assert ver.loc[2, "is_synthetic"] == True
    assert ver.loc[3, "is_synthetic"] == True
    assert ver.loc[1, "is_synthetic"] == False
    assert out[out["driver"] == "HAM"]["is_synthetic"].any() == False


# ──────────────────────────────────────────────────────────────────────────────
# STEP 6 — ground truth  (pins the Abbreviation merge; guards the silent all-NaN)
# ──────────────────────────────────────────────────────────────────────────────
def test_ground_truth_merges_on_abbreviation():
    df = pd.DataFrame({"driver": ["HAM", "VER"], "lap_number": [1, 1]})
    out = _attach_ground_truth(df, _fake_results())

    assert "final_position" in out.columns
    # the merge actually populated — NOT all-NaN (the silent-failure tripwire)
    assert out["final_position"].notna().all()
    assert out.set_index("driver").loc["HAM", "final_position"] == 1


# ──────────────────────────────────────────────────────────────────────────────
# End-to-end: the whole pipeline composes on fake data
# ──────────────────────────────────────────────────────────────────────────────
def test_build_canonical_composes():
    out = build_canonical(
        _fake_raw_laps(),
        _fake_results(),
        track_status=None,   # _merge_track_status is a no-op; per-lap status already present
    )
    # key derived columns all present
    for col in ["cumulative_time", "position", "gap_to_leader", "gap_to_ahead",
                "tyre_age", "is_outlap", "is_inlap", "is_sc_vsc",
                "is_synthetic", "final_position"]:
        assert col in out.columns, f"missing {col}"
    # ground truth populated end-to-end
    assert out["final_position"].notna().all()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\nall {len(fns)} clean.py tests passed")