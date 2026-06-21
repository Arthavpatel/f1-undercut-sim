"""
test_zandvoort_hadjar.py — applying the undercut sim to a real strategic decision:
Hadjar holding P4 at the 2025 Dutch GP. Should he pit to undercut, or stay out?

IMPORTANT CAVEAT: the pace model constants here are fit on HUNGARY 2019.
This test demonstrates the DECISION LOGIC, not a quantitatively valid Zandvoort
sim. For a real Zandvoort answer, rebuild base_pace/deg_rates/reference_age from
2025 Dutch GP data via the data layer (the architecture supports this).

Real-race context (from race reports):
- Hadjar ran P4 essentially the whole race, defending from Leclerc/Russell.
- Zandvoort: very hard to overtake; THREE safety cars; podium came partly via
  Norris's late DNF. This is a 'track position is everything' race.
- Strategic read under test: at a low-overtake, SC-prone track, does staying out
  to hold P4 beat pitting into traffic?
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.sim.undercut import undercut_verdict
from src.sim.forward import CarState


def run_hadjar_stay_out_vs_undercut(static, pit_loss):
    # Hadjar holding P4, with the car ahead (P3) a small gap up the road.
    # Both on similar-age tyres mid-stint. (Values illustrative — Zandvoort-
    # specific gap/age would come from that race's data.)
    hadjar = CarState("HAD", lap_number=40, tyre_age=18, compound="MEDIUM",
                      cumulative_time=2.0, next_compound="HARD")   # 2s behind P3
    rival_ahead = CarState("P3", lap_number=40, tyre_age=18, compound="MEDIUM",
                           cumulative_time=0.0, next_compound="HARD")

    # Zandvoort is hard to overtake → the undercut must gain ENOUGH to clear,
    # and the window is short before SC risk. Test a realistic window.
    verdict = undercut_verdict(hadjar, rival_ahead, static, pit_loss, n_laps=12)
    print("Hadjar undercut verdict (Hungary-fit constants — illustrative):")
    print(verdict)

    # The strategic point: at a low-overtake track, even a 'works=True' undercut
    # that only gains tenths is risky, and SC probability can wipe it out.
    return verdict


if __name__ == "__main__":
    # supply your Hungary-fit static + measured pit_loss when calling
    raise SystemExit("Call run_hadjar_stay_out_vs_undercut(static, pit_loss) from the notebook.")