# f1-undercut-sim

**Does the undercut work?** A deterministic F1 race-strategy simulation engine that turns that question into a number — modeling lap time from base pace, fuel burn and tyre wear, then running the field forward pit-now vs stay-out to diff the result.

### 🔴 [Live interactive demo →](https://arthavpatel.github.io/f1-undercut-sim/)
Drag the inputs (gap, pit-lane loss, tyre age, degradation rate, rival reaction delay) and watch the verdict re-run live.

---

## What it does

Given a gap to a rival and a set of tyre/pit-stop assumptions, the engine answers the strategist's actual question: **if I pit now, do I come out ahead — and by how much?**

It does this by running one deterministic forward-simulation engine twice (pit now vs. hold position) and comparing the resulting gap after N laps, rather than relying on a lookup table or a static rule of thumb.

## How it works

Every lap time the engine produces is one clean sum of three decoupled, independently-fit effects:

```
predicted_lap_time = base_pace[driver] + fuel_effect(lap) + deg_effect(tyre_age, compound)
```

| Layer | What it captures | Fit from |
|---|---|---|
| `base_pace[driver]` | Each driver's reference lap — median of clean green-flag laps | Real lap data |
| `fuel_effect(lap)` | Cars get lighter as fuel burns → laps get faster, expressed relative to mid-race fuel | ~0.035 s/kg burned |
| `deg_effect(age)` | Pure tyre wear, fuel removed — a per-compound linear rate against tyre age | Fuel-corrected stint regression |

**Architecture**, top to bottom:

```
clean · loader  →  pace / fuel / tyre_deg (decoupled models)  →  CarState  →  forward_sim()
```

`forward_sim()` is the one pure function everything composes on: advance the whole field N laps; position falls out of cumulative time, sort-order, nothing more. Two cars or twenty — same loop. Everything else is that function called differently:

- **`undercut_verdict()`** — run it twice (pit now vs. stay out), diff the gap to the rival.
- **`backtest`** — run it with the real pit lap, compare against what actually happened.
- **`monte carlo`** — run it many times with noise on the inputs, turn one verdict into a probability.

## Tyre degradation, fuel removed

Fuel-correct every lap, fit a linear slope per stint, average across the field. What's left is pure wear:

| Compound | Degradation | 
|---|---|
| SOFT | **+0.0877 s/lap** — falls off fastest |
| MEDIUM | +0.0338 s/lap |
| HARD | +0.0413 s/lap — flattest |

## Tech stack

Python · pandas · NumPy · [FastF1](https://github.com/theOehrly/Fast-F1) for lap data

## Getting started

```bash
git clone https://github.com/Arthavpatel/f1-undercut-sim.git
cd f1-undercut-sim
pip install -r requirements.txt
# TODO: confirm entrypoint, e.g.
python run_verdict.py --driver HAD --rival VER --gap 1.2
```

## Project structure

```
TODO — paste your actual file tree here, e.g.:
├── data/           # cleaning & loading
├── models/         # pace.py, fuel.py, tyre_deg.py
├── engine/         # forward_sim.py, undercut_verdict.py, backtest.py, monte_carlo.py
├── docs/           # live interactive demo (index.html)
└── notebooks/       # analysis / output.png generation
```

## Live demo

The `docs/` folder contains a standalone, dependency-free `index.html` (vanilla JS, no build step) served via GitHub Pages — see it live [here](https://arthavpatel.github.io/f1-undercut-sim/).
