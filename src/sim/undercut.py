"""
undercut.py — the undercut verdict. The project's headline question:
"if my driver pits NOW to undercut the car ahead, does it work?"

This is a THIN layer over forward.py. It runs the engine twice
(pit-now vs stay-out), compares where my driver ends up relative to the
rival, and returns a verdict: does it work, and by how much.
"""
from dataclasses import dataclass
from copy import deepcopy

from src.sim.forward import forward_sim, positions_from


@dataclass
class UndercutVerdict:
    works: bool
    time_delta: float
    gap_after_pit: float
    gap_after_stay_out: float

from copy import deepcopy

def undercut_verdict(my_car, rival_car, static, pit_loss, n_laps):

    # ----------------------------
    # Scenario A: pit now
    # ----------------------------
    my_a = deepcopy(my_car)
    rival_a = deepcopy(rival_car)

    my_a.pit_lap = my_a.lap_number

    sim_a = forward_sim(
        [my_a, rival_a],
        static,
        pit_loss,
        n_laps
    )

    gap_a = _gap_to_rival(
        sim_a,
        my_a.driver,
        rival_a.driver
    )

    # ----------------------------
    # Scenario B: stay out
    # ----------------------------
    my_b = deepcopy(my_car)
    rival_b = deepcopy(rival_car)

    my_b.pit_lap = None

    sim_b = forward_sim(
        [my_b, rival_b],
        static,
        pit_loss,
        n_laps
    )

    gap_b = _gap_to_rival(
        sim_b,
        my_b.driver,
        rival_b.driver
    )

    # ----------------------------
    # Compare
    # ----------------------------
    works = gap_a < 0
    time_delta = gap_b - gap_a

    return UndercutVerdict(
        works=works,
        time_delta=time_delta,
        gap_after_pit=gap_a,
        gap_after_stay_out=gap_b,
    )

def _gap_to_rival(cars, my_driver, rival_driver):
    """
    Helper: after a sim, return my_driver's gap to rival_driver in seconds.
    gap = my_cumulative_time - rival_cumulative_time
    (positive = I'm behind, negative = I'm ahead — one convention, used everywhere)
    YOU WRITE: find both cars in the list, subtract their cumulative_times.
    """
    my_car = next(c for c in cars if c.driver == my_driver)
    rival_car = next(c for c in cars if c.driver == rival_driver)
    return my_car.cumulative_time - rival_car.cumulative_time