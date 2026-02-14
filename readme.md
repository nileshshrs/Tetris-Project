# Heuristic-Based Tetris AI with Genetic Optimization

This project implements an AI system for Tetris using heuristic evaluation and a Genetic Algorithm (GA), designed to enhance gameplay strategies, support real-time decision-making, and provide insight into agent behavior in a constrained game environment. The AI evaluates tetromino placements using a weighted cost function and evolves over generations through mutation, crossover, and selection.

> **Note**: This project is AI-only. The game runs in automated mode with the AI making all decisions. Human controls exist but are overridden and not intended for manual play.

## Overview

- **AI Type**: Heuristic-based using weighted board evaluation  
- **Optimization**: Genetic Algorithm (selection, crossover, mutation)  
- **Lookahead**: One-step lookahead (current + next tetromino)  
- **Engine**: Custom Pygame Tetris engine with scoring, ghost pieces, hold, lock delay  
- **Parallel Training**: Multi-tray evaluation using multiprocessing  
- **Evaluation**: Based on score, lines, survival time, and average move quality  

## Project Structure

```text
Tetris-Project/
├── AI/
│   └── TetrisAI.py             # Core AI logic and cost evaluation
├── GA/
│   ├── genetic_algorithm.py    # GA evolution logic
│   ├── optimize.py             # GA training pipeline
│   ├── tetris_ai.py            # Agent wrapper for GA
│   └── gauntlet.py             # Gauntlet comparison of top agents
├── notebooks/
│   ├── agent_analysis.ipynb
│   ├── extract_agent.ipynb
│   ├── ga_plots.ipynb
│   └── gauntlet_comparison.ipynb
├── results/
│   ├── GA/                     # GA generation logs
│   └── gauntlet/               # Evaluation logs
├── Tetris/
│   ├── assets/
│   │   ├── graphics/
│   │   └── sound/
│   ├── game.py
│   ├── main.py                 # Entry point (AI-controlled Tetris)
│   ├── held.py
│   ├── lines.py
│   ├── preview.py
│   ├── score.py
│   ├── settings.py
│   └── timers.py
├── requirements.txt
└── README.md
```
---

## How to Run

### 1. **Run Tetris AI (Solo Play)**

Launch a solo game session where the AI plays automatically using the heuristic evaluation function. Human controls exist but are ignored; manual play is disabled.

```bash
python Tetris/main.py
```
### 2. **Train AI Agents using the Genetic Algorithm**

Train a population of AI agents using a genetic algorithm. The training process evolves agent weights over generations by evaluating their performance on key metrics such as score, lines cleared, level reached, and survival time. Agents are selected, mutated, and crossed over based on their fitness, resulting in increasingly optimized gameplay strategies.

```bash
python GA/optimize.py
```

### 3. **Evaluate Top Agents in Gauntlet Mode**

Run a gauntlet-style tournament to compare the top-performing agents after training. This evaluation pits the best agents against each other in a series of head-to-head matches, logging their performance and enabling detailed analysis of agent strategies and effectiveness.

```bash
python GA/gauntlet.py
```
---

## Cost Function Features

The AI evaluates every possible placement of the current tetromino, using one-step lookahead, with a linear cost function made up of these board features:

- Aggregate Height
- Number of Holes
- Bumpiness
- Blockades
- Well Depth
- Almost-Filled Lines
- 1-Line, 2-Line, 3-Line Clears
- Tetris (4-Line Clears)
- Line Clear Bonuses

Each feature is multiplied by an individual weight. These weights are optimized by the genetic algorithm during training (mutation, crossover, and selection).

---

## Logging and Analysis

- `results/GA/`: Per-generation and per-agent performance metrics (CSV format: score, lines, weights, etc.)
- `results/gauntlet/`: Head-to-head comparison logs for top agents
- `notebooks/`: Jupyter notebooks for analyzing GA performance, agent fitness, weight convergence, and gameplay metrics

---
## Title

HEURISTIC-GA GREEDY LOOKAHEAD TETRIS AI


## Dependencies

Install the required Python packages before running any scripts:

```bash
pip install -r requirements.txt
```

---

## Changelog

For detailed information about updates, improvements, and version history, see the **[CHANGELOG.md](CHANGELOG.md)**.

### Recent Updates

| Date | Version | Description |
|------|---------|-------------|
| 2026-02-07 | Phase 1 | **SRS Implementation** — Static rotation tables, official wall kicks, zero runtime math |
| 2026-02-07 | Phase 1 ✅ | **SRS Complete** — I-piece fixed to have 4 distinct rotation states per official SRS spec |
| 2026-02-14 | Phase 1 Polish | **AI 4-rotation fix**, CCW rotation keybinding, tuple-based rotation, dead code cleanup |
| 2026-02-14 | Phase 2 ✅ | **Atomic Logic Core** — `core.py` headless engine, shadow validation, zero collision mismatches |

---

*For the complete changelog with technical details, benefits, and code examples, visit [CHANGELOG.md](CHANGELOG.md).*
