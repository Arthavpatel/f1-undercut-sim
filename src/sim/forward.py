"""
forward.py — the deterministic forward-simulation engine.
THE core of the project. Given the field's current state and each car's pit
decision, advance the race N laps and return the new state. Position falls out
of cumulative time (sort-order), exactly as in the data layer.

Everything composes on this one function:
  - undercut verdict = run it twice (pit-now vs stay-out), diff the result
  - backtest        = run it with the REAL pit lap, compare to reality
  - Monte Carlo     = run it many times with noise on the inputs
"""
from dataclasses import dataclass
from copy import deepcopy

from src.models.pace import predicted_lap_time
from src.models.tyre_deg import deg_effect  # noqa: F401  (used via predicted_lap_time)


@dataclass
class RaceConstants:
    """
    Race-level invariants — computed ONCE, identical for every car and every lap.
    Bundled so advance_one_lap's signature stays clean.
    """
    base_pace: object          # pd.Series: driver -> base pace (Timedelta)
    fuel_effect_func: object   # callable: lap_number -> fuel correction (seconds)
    deg_rates: dict            # compound -> degradation rate (s/lap)
    reference_age: dict        # compound -> reference tyre age


@dataclass
class CarState:
    """Dynamic per-car state that EVOLVES as the race advances."""
    driver: str
    lap_number: int
    tyre_age: int
    compound: str
    cumulative_time: float          # seconds — the master quantity; position = sort-order
    pit_lap: int | None = None      # the lap THIS car pits on (None = no pit in window)
    next_compound: str | None = None  # compound to switch to when pitting
    has_pitted: bool = False        # so we only apply the pit once


def advance_one_lap(car, static, pit_loss):
    """
    Advance ONE car by ONE lap. Pure: returns a NEW CarState, never mutates `car`.
    `static` is a RaceConstants bundle.
    """
    new_car = deepcopy(car)

    # 1. this lap's time, from the car's CURRENT state (old tyre if this is the pit lap)
    lap_time = predicted_lap_time(
        new_car.driver,
        new_car.lap_number,
        new_car.tyre_age,
        new_car.compound,
        static.base_pace,
        static.fuel_effect_func,
        static.deg_rates,
        static.reference_age,
    )
    new_car.cumulative_time += lap_time

    # 2. pit handling — the ONLY branching logic, and the whole undercut mechanism
    if (not new_car.has_pitted) and (new_car.lap_number == new_car.pit_lap):
        new_car.cumulative_time += pit_loss          # time lost in the pit lane
        new_car.compound = new_car.next_compound     # fresh set, new compound
        new_car.has_pitted = True
        # tyre_age sequence across a stop: the pit lap ran on the OLD tyre; we set
        # age to 0 here so the NEXT lap's increment makes it 1 — matching clean.py's
        # convention that the first lap on a set is age 1. Trace: ...,16, [pit ->0], 1, 2,...
        new_car.tyre_age = 0
    else:
        new_car.tyre_age += 1

    # 3. advance the lap counter
    new_car.lap_number += 1
    return new_car


def forward_sim(cars, static, pit_loss, n_laps):
    """
    Advance the WHOLE field n_laps. Pure function — the engine.
    cars: list[CarState] (2 for an undercut test, 20 for the full field — same loop).
    """
    current_cars = cars
    for _ in range(n_laps):
        next_cars = [advance_one_lap(car, static, pit_loss) for car in current_cars]
        current_cars = next_cars
    return current_cars


def positions_from(cars):
    """
    Track position = sort-order of cumulative_time (the Phase-1 master insight,
    now at the heart of the sim). Returns drivers ordered P1..PN.
    """
    sorted_cars = sorted(cars, key=lambda c: c.cumulative_time)
    return [car.driver for car in sorted_cars]