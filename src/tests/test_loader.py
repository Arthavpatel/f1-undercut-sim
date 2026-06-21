"""Unit test for clean.py — runs with a fake dataframe, NO network/FastF1.
This is the payoff of keeping clean.py pure: fast, offline, deterministic."""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root

from src.data_layer.clean import _select_lap_columns


def _fake_laps():
    """Minimal stand-in with the FastF1 columns _select_lap_columns expects."""
    return pd.DataFrame({
        "Driver":     ["HAM", "VER"],
        "Team":       ["Mercedes", "Red Bull"],
        "LapNumber":  [1, 1],
        "Stint":      [1, 1],
        "Position":   [1, 2],
        "LapTime":    pd.to_timedelta(["0:01:18.5", "0:01:18.9"]),
        "Time":       pd.to_timedelta(["0:03:18.5", "0:03:19.9"]),
        "LapStartTime": pd.to_timedelta(["0:02:00", "0:02:01"]),
        "Compound":   ["MEDIUM", "MEDIUM"],
        "TyreLife":   [1, 1],
        "PitInTime":  [pd.NaT, pd.NaT],
        "PitOutTime": [pd.NaT, pd.NaT],
        "IsAccurate": [True, True],
        "TrackStatus":["1", "1"],
        # deliberately include an EXTRA column the map should DROP:
        "SpeedST":    [310, 308],
    })


def test_select_renames_and_drops():
    out = _select_lap_columns(_fake_laps())

    # canonical names exist
    assert "driver" in out.columns
    assert "lap_time" in out.columns

    # raw FastF1 names are gone (renamed, not duplicated)
    assert "Driver" not in out.columns

    # columns with no consumer were dropped
    assert "SpeedST" not in out.columns

    # no rows lost
    assert len(out) == 2


if __name__ == "__main__":
    test_select_renames_and_drops()
    print("clean smoke test passed")