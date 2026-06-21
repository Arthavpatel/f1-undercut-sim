"""
loader.py — the only module that talks to FastF1 / the network.
Returns raw FastF1 objects; clean.py shapes them into the canonical schema.
"""
import fastf1 as f1
from pathlib import Path

# --- cache setup (boilerplate) ---
PROJECT_ROOT = Path(__file__).resolve().parents[2] 
CACHE_DIR = PROJECT_ROOT / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
f1.Cache.enable_cache(str(CACHE_DIR))


class SessionLoadError(Exception):
    pass


def load_session(year: int, gp: str, session: str = "R"):
    try:
        session_obj = f1.get_session(year, gp, session)
        session_obj.load()
        if session_obj.laps.empty:
            raise SessionLoadError(
                f"No lap data found for {year} {gp} {session}"
            )
        return session_obj

    except SessionLoadError:
        raise

    except Exception as e:
        raise SessionLoadError(
            f"Failed to load {year} {gp} {session}: {e}"
        ) from e
    

def get_laps(session_obj):
    return session_obj.laps

def get_results(session_obj):
    try:
        results = session_obj.results
        if results.empty:
            raise SessionLoadError("No results data found")
        return results

    except SessionLoadError:
        raise

    except Exception as e:
        raise SessionLoadError(
            f"Failed to retrieve results data: {e}"
        ) from e


def get_track_status(session_obj):
    try:
        track_status = session_obj.track_status
        if track_status.empty:
            raise SessionLoadError("No track status data found")
        return track_status

    except SessionLoadError:
        raise

    except Exception as e:
        raise SessionLoadError(
            f"Failed to retrieve track status data: {e}"
        ) from e