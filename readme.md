# Heuristic-Based Tetris AI with Genetic Optimization

This project implements an AI system for Tetris using heuristic evaluation and a Genetic Algorithm (GA), designed to enhance gameplay strategies, support real-time decision-making, and provide insight into agent behavior in a constrained game environment. The AI evaluates tetromino placements using a weighted cost function and evolves over generations through mutation, crossover, and selection.

> **Note**: This project is AI-only. The game runs in automated mode with the AI making all decisions. Human controls exist but are overridden and not intended for manual play.

## Overview

- **AI Type**: Heuristic-based using weighted board evaluation (zero object instantiation — pure integer math, bit-board search)
- **Architecture**: **Dual-Worker Parallel System** (evaluates "Play" vs "Hold" branches simultaneously)
- **Optimization**: Genetic Algorithm (selection, crossover, mutation) with a hand-tuned **baseline agent** as a reference
- **Lookahead**: **Hold-aware one-step lookahead** (compares best placement of current piece vs best placement of held piece, each with its own 1-step lookahead)
- **Engine**: Custom Pygame Tetris engine with headless `TetrisCore` logic layer (zero Pygame dependency)
- **Training / benchmarking**: a **headless simulator** (seeded pieces, piece cap, virtual clock) run in parallel worker processes — no window, no real-time waiting, results independent of machine load
- **Fitness**: mean game score over several seeded games, weighted by a built-in target: survive as often as the baseline and make at least 15× the baseline's Tetrises (full credit only when both are met)

## Project Structure

```text
Tetris-Project/
├── AI/
│   ├── evaluator.py            # Shared heuristic evaluator: fast bit-board search (+ the slow reference version it is tested against)
│   ├── worker.py               # Parallel AI worker (handles a single branch of the search)
│   ├── TetrisAI.py             # Dual-worker controller (manages PLAY/HOLD pipes and move execution)
│   └── GA/
│       ├── genetic_algorithm.py # GA evolution logic + fitness
│       ├── simulator.py         # Headless game simulator (seeded pieces, piece cap, virtual clock)
│       ├── optimize.py          # GA training pipeline (uses the simulator)
│       ├── tetris_ai.py         # Dual-worker GA agent (matches runtime architecture)
│       └── gauntlet.py          # Benchmark: agents play identical seeded games, paired comparison vs baseline
├── notebooks/
│   ├── agent_analysis.ipynb
│   ├── extract_agent.ipynb
│   ├── ga_plots.ipynb
│   └── gauntlet_comparison.ipynb
├── results/
│   ├── GA/run_N/                # ga_log.csv, agent_log.csv, baseline_log.csv, ga_checkpoint.pkl, config.json
│   └── gauntlet/from_run_N/     # results_<agent>.csv, summary.csv, config.json (agents of GA run_N)
├── Tetris/
│   ├── assets/
│   │   ├── graphics/
│   │   └── audio/
│   ├── core.py                  # Headless logic engine (zero Pygame, pure integer)
│   ├── game.py
│   ├── main.py                  # Entry point (AI-controlled Tetris)
│   ├── held.py
│   ├── lines.py
│   ├── preview.py
│   ├── score.py
│   ├── settings.py              # Static SRS rotation tables + kick data
│   └── timers.py
├── requirements.txt             # game, AI, GA, plots
├── requirements-notebooks.txt   # ipykernel, only needed to run the notebooks
├── CHANGELOG.md
└── readme.md
```
---

## Setup

From the project folder (Windows):

```bash
py -m venv venv
source venv/Scripts/activate                  # Git Bash   (PowerShell: .\venv\Scripts\Activate.ps1)
pip install -r requirements.txt
pip install -r requirements-notebooks.txt     # optional: only to run the notebooks
```

Without activating the environment you can call its Python directly, e.g. `venv/Scripts/python.exe Tetris/main.py`.

On Python 3.14+ `requirements.txt` installs `pygame-ce` (a drop-in replacement) because `pygame` has no prebuilt packages there.

---

## How to Run

### 1. **Run Tetris AI (Solo Play)**

Launch a solo game session where the AI plays automatically using the heuristic evaluation function. Human controls exist but are ignored; manual play is disabled.

```bash
python Tetris/main.py
```

### 2. **Train AI Agents using the Genetic Algorithm**

Train a population of weight vectors with a genetic algorithm, using the headless simulator (no window, no real-time waiting).

- Each agent plays `--games` seeded games per generation. Game slot *k* uses the same piece sequence for **every** agent in that generation, so score differences come from the weights. The sequences change every generation, so agents can't over-fit to one.
- Each game lasts `--max-time` seconds of *virtual* game time at `--ai-delay` ms per piece (65 s at 130 ms = 500 pieces). The simulator never waits: it computes each decision as fast as the CPU allows, so the real time per game is roughly `pieces x time per decision`.
- Fitness = mean game score (+1 per piece placed) × **S** × **T**, where the two factors are 1.0 when the target is met:
  - **S (survival)** = (fraction of games survived)^`--survival-power` (default 4): surviving every game like the baseline keeps 100%, losing 1 of 4 games keeps 32%, 2 of 4 keeps 6%.
  - **T (Tetris target)** = min(1, Tetrises per piece / target)^`--tetris-power` (default 1), where the target is `--target-tetris-ratio` (default **15**) × the baseline's Tetris rate. The baseline's rate (0.0008 Tetrises per piece, i.e. 0.8 per 1,000-piece game) and the 15× are embedded as constants in `genetic_algorithm.py`; 15× is the multiple every candidate of the first GA run reached in the gauntlet (15.0–26.5×).
  - **D (near-death, optional)** = (1 − share of pieces placed while the stack was ≥ `--danger-height` rows)^`--danger-power` (default power 0 = off). It rates how risky an agent plays, not only whether it dies.
  - The baseline agent is scored with S (and D) only (it is the reference the Tetris target is measured against). `--survival-power 0 --tetris-power 0` gives the earlier score-only fitness.
- Survival is only measured over the training game length, so use games as long as the gauntlet's (`--max-time 130` = 1000 pieces) when survival matters.
- A **baseline agent** (the hand-tuned default weights) plays the same seeds every generation but is never bred; `RelBest` / `RelAvg` in the log are the population's fitness divided by its fitness, which removes "this generation's pieces were easy/hard" noise. Disable with `--no-baseline`.
- Output goes to a new `results/GA/run_N/` (`ga_log.csv`, `agent_log.csv`, `baseline_log.csv`, `ga_checkpoint.pkl`, `config.json`). Runs are numbered automatically and never deleted. Continue a run with `--resume run_N` (keep `--pop` the same).

```bash
python AI/GA/optimize.py --pop 12 --games 4 --max-time 60 --generations 10    # small test
python AI/GA/optimize.py --workers 8                                           # defaults, but leave some CPU free
python AI/GA/optimize.py --pop 12 --games 4 --max-time 130 --generations 30 --workers 8   # gauntlet-length games: survival counts
python AI/GA/optimize.py                                                       # defaults: pop 50, 5 games, 65 s, 50 generations
```

| Flag | Default | Meaning |
|---|---|---|
| `--pop` | 50 | agents per generation |
| `--games` | 5 | seeded games per agent per generation (more = less noisy ranking, slower; 1 is only good for a smoke test) |
| `--max-time` | 65 | virtual seconds per game (÷ `--ai-delay` = piece cap) |
| `--ai-delay` | 130 | ms of game time per piece (130 ≈ fastest recorded 40-line sprint pace, 195 = Guinness sprint pace, 60 = standalone AI) |
| `--generations` | 50 | last generation number to reach |
| `--workers` | all cores | worker processes; lower it to keep the CPU below 100% |
| `--seed` | 12345 | base seed of the run |
| `--resume run_N` | — | continue an existing run |
| `--survival-power` | 4 | survival weighting of the fitness (0 = score only) |
| `--target-tetris-ratio` | 15 | Tetris target built into the fitness: full credit needs this many times the baseline's Tetrises |
| `--tetris-power` | 1 | how strongly missing the Tetris target is punished (0 = off) |
| `--danger-power` | 0 | near-death penalty: fitness × (1 − share of pieces placed with the stack ≥ danger height)^power (0 = off) |
| `--danger-height` | 16 | stack height (of 20 rows) counted as dangerous; higher = gentler, lower = harsher |
| `--inject NAME…` | — | add known good agents to generation 0 (currently `g26`) |
| `--no-baseline` | — | don't play the baseline agent each generation |

The best-fitness line bounces from generation to generation (different piece sequences each time); judge progress by the population average and `RelBest`/`RelAvg`, then confirm the best candidates in the gauntlet on fresh seeds.

### 3. **Evaluate Top Agents in Gauntlet Mode**

Benchmark agents on identical seeded games in the headless simulator. Every agent plays the same piece sequences (on seeds the training never used), so the comparison is paired; results are logged to `results/gauntlet/from_run_N/` (named after the GA run that was tested; a repeat gets a `_2` suffix) and a summary table is printed. The **baseline agent** (default weights) is always included and is the reference for the paired comparison. This is the step that picks the real winner.

```bash
python AI/GA/gauntlet.py --from-run run_1          # best candidates of a GA run (top 5 by fitness + last generation) vs baseline
python AI/GA/gauntlet.py --from-run run_1 --top 8  # more candidates
python AI/GA/gauntlet.py --set final_run           # a weight set defined in gauntlet.py
python AI/GA/gauntlet.py --from-run run_1 --workers 8
```

Options: `--from-run`, `--top`, `--set`, `--games` (20), `--max-time` (130 s = 1000 pieces), `--ai-delay`, `--seed`, `--workers`, `--no-baseline`, `--target-tetris-ratio`, `--target-survival-gap`, `--danger-height` (16; adds `MeanPeakHeight` and `MeanDangerShare` to `summary.csv`).

**Target check.** The summary table also says whether each agent meets the target: survive as often as the baseline (within `--target-survival-gap`, default 0.05 = one death in 20 games) **and** make at least `--target-tetris-ratio` (default 15, the same target that is built into the training fitness) times the baseline's Tetrises per game. Each agent is marked `PASS` or `fail` (columns `SurvivalRate`, `TetrisRatio`, `MeetsTarget` in `summary.csv`).

Each gauntlet run folder contains one `results_<agent>.csv` per agent (per-game rows), `summary.csv` (one row per agent, including the paired difference against the reference), and `config.json` (the exact weights, seeds and settings that were tested).

### 4. **Analyse results in the notebooks**

Open the notebooks in `notebooks/` (they need `requirements-notebooks.txt`). Each one finds the project folder itself and ends with a cell that shows the newest run; pass another run's file (for example `GA_DIR / "run_3" / "ga_log.csv"`) to look at an older one.

---

## Cost Function Features

The AI evaluates every possible placement for BOTH the current tetromino and the held tetromino (if available), using one-step lookahead for each branch:

- Aggregate Height
- Number of Holes
- Blockades (filled cells sitting above a hole)
- Bumpiness
- Almost-Filled Lines
- Fills Well (reward when the piece lands in the deepest well)
- Line Clear Bonuses for 4-line (Tetris), 3-line, 2-line and 1-line clears

Weight order: `[agg_height, holes, blockades, bumpiness, almost_full, fills_well, clear_4, clear_3, clear_2, clear_1]`. Each feature is multiplied by an individual weight; these weights are optimized by the genetic algorithm during training (mutation, crossover, and selection).

### Search speed

`AI/evaluator.py` stores each board row and column as an integer and only recomputes the few columns and rows a piece touches (a bit-board search). It returns exactly the same moves and scores as the original cell-by-cell implementation, which is kept as `find_best_move_scored_reference` for verification, and is roughly 4-7x faster. The real game's workers and the simulator both use it.

## Known limitations / not implemented

- Scoring is "lines x level" only (levels and speed-up are switched off): no T-spins, combos, back-to-back or perfect-clear bonuses, no garbage lines / versus mode.
- The AI looks at the current piece, the next piece and the held piece (the preview shows 3, the AI uses 1) and only considers straight-down drops (no slides under overhangs).
- The simulator uses a virtual clock (time = pieces x AI delay). It does not model gravity, lock delay or worker latency; it assumes the AI is always faster than gravity.
- No menu, pause, restart or human play.

---

## Logging and Analysis

- `results/GA/run_N/`: Per-generation (`ga_log.csv`), per-agent (`agent_log.csv`) and baseline (`baseline_log.csv`) metrics (score, lines, weights, deaths, etc.). `Time` columns are virtual game seconds. Each run gets the next free number and old runs are never deleted automatically.
- `results/gauntlet/from_run_N/`: Per-agent game results, `summary.csv` and `config.json` of every gauntlet run (`set_<name>/` for weight sets).
- `notebooks/`: Jupyter notebooks for analyzing GA performance, agent fitness, weight convergence, paired gauntlet comparisons and the baseline-relative curve.

---

## Title

HEURISTIC-GA GREEDY LOOKAHEAD TETRIS AI

---

## Changelog

For detailed information about updates, improvements, and version history, see the **[CHANGELOG.md](CHANGELOG.md)**.

### Recent Updates

| Date | Version | Description |
|------|---------|-------------|
| 2026-11-09 | Simulator Training ✅ | **Headless simulator + fitness v3 + baseline agent** — Seeded, parallel, machine-independent training and gauntlet with a virtual clock; fitness = mean game score; the default-weights baseline plays every generation for a luck-free progress curve; per-run result folders with config; notebooks and requirements updated. |
| 2026-11-09 | Fast Search ✅ | **Bit-board move search** — Identical moves and scores to the reference implementation (verified on 1,400 random boards and 8 whole games), ~4-7x faster. |
| 2026-11-09 | Blockades Fix ✅ | **`blockades` feature** now counts filled cells above the lowest hole (it used to equal roughly the number of filled cells). Weights need retuning. |
| 2026-03-28 | Weight Re-tune ✅ | **Default Weight Re-tuning & Fitness v2** — Re-tuned defaults for corrected fills_well sign (agg_height 3.5, holes 6.0, boosted small clears). Fitness v2: 8-component with efficiency gate, Tetris rate bonus, consistency gate, stronger death penalty. |
| 2026-03-28 | GA Overhaul ✅ | **GA Engine Overhaul** — Population 10→50, stagnation detection + mutation surge, diversity injection, median fitness, self-crossover prevention, weight bounds widened to [0,30], seeded initialization. |
| 2026-03-28 | Phase 5 (Part 1) ✅ | **GA Fitness Overhaul** — Redesigned fitness to reward efficiency (lines/min), Tetris dominance (8× bonus), sqrt-based survival, and tiered death penalties. Timeout raised to 600s. |
| 2026-03-28 | Phase 4 (Part 1) ✅ | **Worker Lifecycle Cleanup** — Added `close()`/context manager to `Main`, cleanup calls in `optimize.py` and `gauntlet.py` to prevent zombie worker processes. |
| 2026-03-28 | Phase 3 (Part 1) ✅ | **fills_well Reward Sign Fix** — Updated `AI/evaluator.py` so `fills_well` now reduces cost (reward) instead of increasing cost (penalty); this changes GA weight semantics. |
| 2026-03-28 | Phase 2 (Part 1) ✅ | **Shared Evaluator Module** — Added `AI/evaluator.py` and refactored `AI/TetrisAI.py`, `AI/worker.py`, and `AI/GA/tetris_ai.py` to use one shared heuristic/cost/search implementation. |
| 2026-02-07 | Phase 1 | **SRS Implementation** — Static rotation tables, official wall kicks, zero runtime math |
| 2026-02-07 | Phase 1 ✅ | **SRS Complete** — I-piece fixed to have 4 distinct rotation states per official SRS spec |
| 2026-02-14 | Phase 1 Polish | **AI 4-rotation fix**, CCW rotation keybinding, tuple-based rotation, dead code cleanup |
| 2026-02-14 | Phase 2 ✅ | **Atomic Logic Core** — `core.py` headless engine, shadow validation, zero collision mismatches |
| 2026-02-28 | Phase 3 ✅ | **Quantum AI Refactor** — Zero object instantiation, pure integer math, 4-rotation eval, vertical reachability, move caching |
| 2026-02-28 | Phase 2 & 3 Polish | **Performance polish** — Removed shadow validation, single-pass board features, zero-copy line counting, simplified `core_grid` sync |
| 2026-03-01 | Final Polish | **Code hygiene** — Fixed `w1` set→list bug, `fills_well` boundary guard, removed all dead code (`core_grid`, `TETROMINOS_WEIGHTS`, `create_new_tetromino_called`, unused AI params) |
| 2026-03-01 | Polish Pass 2 | **Robustness & cleanup** — Removed `score.py` border, fixed `timers.py` `set_interval()` no-op, robust AI import path, removed dead code (`current_bag`, `tetromino_touching_floor`, unused imports), tabs→spaces |
| 2026-03-07 | Phase 4 ✅ | **High-Performance Renderer** — Removed all Sprite Groups and `Block` class, pure integer `game_data`, efficient `bg_surface` pixel baking |
| 2026-03-07 | Phase 5 ✅ | **Modern Mechanics** — Implemented Lock Delay (Infinity Rule), max move limiter, and professional DAS/ARR keyboard timings |
| 2026-03-21 | Phase 6 ✅ | **Async Multiprocessing** — AI worker process, zero-stall 60 FPS gameplay, full multiprocessing GA support |
| 2026-03-21 | Phase 6 Polish | **Async Execution Throttle** — Fixed visual overlapping by delaying hard drops without stalling sideways shifts |
| 2026-03-21 | Audio | **Targeted BGM** — Added "Tetris Effect" In-game Mix audio support with auto-mute during headless GA training |

### Update

| Phase | Date | Files | Description |
|------|------|-------|-------------|
| Phase 1 (Part 1) | 2026-03-27 | `Tetris/settings.py`, `Tetris/main.py` | **Per-Game RNG Isolation** — `create_7bag()` and `get_next_tetromino()` now accept an optional RNG instance, and each `Main` object creates its own `random.Random` so GA trays no longer share piece-sequence state. |
| Phase 2 (Part 1) | 2026-03-28 | `AI/evaluator.py`, `AI/TetrisAI.py`, `AI/worker.py`, `AI/GA/tetris_ai.py` | **Shared Evaluator Extraction** — Consolidated duplicated feature extraction, line-clear counting, cost function, lookahead scoring, and best-move search into `AI/evaluator.py` as a single source of truth with zero Pygame dependency. |
| Phase 3 (Part 1) | 2026-03-28 | `AI/evaluator.py` | **fills_well Sign Correction** — Flipped the `fills_well` term in the shared cost function so well-filling is rewarded instead of penalized. Existing GA checkpoints were trained under inverted semantics and should be retrained. |
| Phase 4 (Part 1) | 2026-03-28 | `Tetris/main.py`, `AI/GA/optimize.py`, `AI/GA/gauntlet.py` | **Worker Lifecycle Cleanup** — Added `close()` and context manager to `Main`; GA trays and gauntlet games now explicitly clean up worker processes after each game finishes. |
| Phase 5 (Part 1) | 2026-03-28 | `AI/GA/genetic_algorithm.py`, `AI/GA/optimize.py` | **GA Fitness Overhaul** — Redesigned fitness to reward efficiency, Tetris dominance, sqrt survival, and tiered death penalties. Training timeout increased to 600s. |
| Phase 6 (Part 1) | 2026-04-03 | `AI/GA/gauntlet.py` | **Gauntlet Cleanup** — Implemented auto-versioning for result folders, fixed timeout comments, and ensured redundant worker processes are shut down after every match. |
| Phase 1 (Part 2) | 2026-04-03 | `AI/TetrisAI.py`, `AI/worker.py`, `AI/evaluator.py`, `Tetris/game.py` | **Hold-Aware Dual-Worker Architecture** — Added parallel evaluation of PLAY/HOLD branches using two async workers. Replaced 2-step lookahead (too slow) with hold-aware 1-step search for real-time responsiveness. |
| Weight Re-tune | 2026-04-03 | `AI/TetrisAI.py`, `AI/worker.py` | **Baseline Revert** — Restored proven-stable heuristic weights to resolve premature AI death caused by experimental weights. |
| GA Overhaul | 2026-03-28 | `AI/GA/genetic_algorithm.py`, `AI/GA/optimize.py` | **GA Engine Overhaul** — Population scaled to 50 with elite=4, stagnation detection with adaptive mutation surge, diversity injection when pop converges, median-of-trays fitness, self-crossover prevention, weight bounds [0,30], seeded initialization, and enhanced checkpoint migration. |

---

*For the complete changelog with technical details, benefits, and code examples, visit [CHANGELOG.md](CHANGELOG.md).*
