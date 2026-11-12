"""
GA training pipeline (headless simulator).

Every agent plays GAMES seeded games per generation, each limited to a budget of
virtual game time (--max-time seconds at --ai-delay ms per piece, i.e. a piece cap). All agents in a generation play the SAME seeds (so ranking isn't
decided by piece-sequence luck), and the seeds change every generation (so
agents can't overfit to a fixed sequence). Games run in parallel worker
processes with no Pygame display, no AI delay and no real time, so results
depend only on weights + seed, not on how busy the machine is.

Usage:
    python AI/GA/optimize.py                      # new run in results/GA/run_<N+1>
    python AI/GA/optimize.py --resume run_6       # continue an existing run
    python AI/GA/optimize.py --pop 20 --games 3 --max-time 12 --generations 5   # quick test
"""

import argparse
import csv
import json
import multiprocessing
import os
import re
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from genetic_algorithm import GA
from simulator import DANGER_HEIGHT, play_job

N_WEIGHTS = 10

RESULTS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'results', 'GA')

W_NAMES = ["AggHeight", "Holes", "Blockades", "Bumpiness", "AlmostFull",
           "FillsWell", "ClearBonus4", "ClearBonus3", "ClearBonus2", "ClearBonus1"]

# Same column names as the original agent_log.csv (notebooks/agent_analysis.ipynb reads
# AvgScore / AvgTime / AvgNumTetris), with the new fields appended at the end.
# AvgLevel is always 1 (levels are switched off); AvgTime is virtual game time in seconds.
AGENT_LOG_HEADER = (
    ["Generation", "AgentID", "AvgScore", "AvgLines", "AvgLevel", "AvgTime"]
    + [f"W{i+1}" for i in range(N_WEIGHTS)]
    + ["AvgNum1Line", "AvgNum2Line", "AvgNum3Line", "AvgNumTetris"]
    + ["Fitness", "AvgPieces", "AvgLinesPerSec", "Deaths"]
    + ["AvgPeakHeight", "AvgDangerShare"]
)

GA_LOG_HEADER = (
    ["Generation", "BestAgentID", "BestFitness", "AvgFitness", "WorstFitness", "FitnessStd",
     "BestScore", "BestLines", "BestPieces", "BestTime", "BestLinesPerSec", "BestDeaths",
     "Num1Line", "Num2Line", "Num3Line", "NumTetris"]
    + [f"W{i+1}:{n}" for i, n in enumerate(W_NAMES)]
    # Baseline comparison (appended last so existing columns keep their names/order):
    #   BaselineFitness = the reference agent's fitness on this generation's seeds
    #   RelBest / RelAvg = BestFitness / AvgFitness divided by BaselineFitness
    + ["BaselineFitness", "RelBest", "RelAvg"]
)

# The reference agent. It plays the same seeds as everyone else every generation, but it is
# NOT part of the population (never selected, bred or mutated). Dividing the population's
# fitness by its fitness cancels out "this generation's piece sequences were easy/hard".
# These are the hand-tuned default weights used by TetrisAI.py / worker.py.
BASELINE_WEIGHTS = [1.275, 4.0, 1.2, 0.8, 0.5, 3.0, 20, 5, 2, 0.1]

BASELINE_LOG_HEADER = [
    "Generation", "Fitness", "AvgScore", "AvgLines", "AvgPieces", "AvgTime", "AvgLinesPerSec", "Deaths",
    "AvgNum1Line", "AvgNum2Line", "AvgNum3Line", "AvgNumTetris",
    "AvgPeakHeight", "AvgDangerShare",
]

# Known-good starting points for generation 0
SEED_WEIGHTS = [
    [3.5, 6.0, 1.5, 1.5, 0.8, 1.5, 20, 8, 4, 2],        # re-tuned defaults (pre-blockades-fix)
    BASELINE_WEIGHTS,                                   # legacy manual-tuned baseline (same as the reference agent)
]

# Optional warm start (--inject g26): agents found by an earlier run, put into generation 0 next to
# the seeds above. Without them a run has to find the Tetris-building style by chance (3 of 5 runs
# never did). Weights are the full-precision values from results/gauntlet/from_run_1/config.json.
INJECTED_AGENTS = {
    # GA run_1 (seed 11111, danger 16/12), generation 26: 98.3% survival, 15.4x the baseline's Tetrises
    # over 60 gauntlet games (seed 1,000,000).
    "g26": [4.738595880072, 22.352468674973, 10.316636145297, 8.386070325721, 27.747232919654,
            6.855264518753, 18.757195771304, 15.394482119433, 5.331512132249, 3.408419513106],
}


def parse_args():
    ap = argparse.ArgumentParser(description="Train Tetris AI weights with a GA (headless).")
    ap.add_argument("--generations", type=int, default=50)
    ap.add_argument("--pop", type=int, default=50, help="population size")
    ap.add_argument("--games", type=int, default=5, help="seeded games per agent per generation")
    ap.add_argument("--max-time", type=float, default=65.0,
                    help="game-time budget per game, in virtual seconds (pieces = max_time / ai_delay)")
    ap.add_argument("--ai-delay", type=int, default=130,
                    help="game time in ms charged per piece. Default 130 = the GA agent's delay "
                         "(~7.7 pieces/sec, near the fastest recorded 40-line sprint). "
                         "Others: 195 = Guinness sprint pace (5.135 PPS), 60 = standalone TetrisAI")
    ap.add_argument("--workers", type=int, default=0, help="worker processes (0 = all cores)")
    ap.add_argument("--seed", type=int, default=12345, help="base seed for the whole run")
    ap.add_argument("--out", type=str, default=RESULTS_ROOT, help="folder that holds run_N folders")
    ap.add_argument("--resume", type=str, default=None, help="existing run folder name to continue (e.g. run_6)")
    ap.add_argument("--survival-power", type=float, default=GA.SURVIVAL_POWER,
                    help="fitness = mean score x (fraction of games survived)^power. Default 4: survive every game "
                         "like the baseline first, then rank by score (Tetrises). 0 = score only (old fitness v3)")
    ap.add_argument("--target-tetris-ratio", type=float, default=GA.TARGET_TETRIS_RATIO,
                    help="Tetris target built into the fitness: full credit needs at least this many times the "
                         "baseline's Tetrises (default 15, see genetic_algorithm.py)")
    ap.add_argument("--tetris-power", type=float, default=GA.TETRIS_POWER,
                    help="how strongly missing the Tetris target is punished (1 = proportionally, 0 = off)")
    ap.add_argument("--danger-power", type=float, default=GA.DANGER_POWER,
                    help="near-death penalty: fitness x (1 - share of pieces placed with the stack >= --danger-height "
                         "rows)^power. 0 = off (default); ~10 makes a 3%% share cost about 26%% of the fitness")
    ap.add_argument("--danger-height", type=int, default=DANGER_HEIGHT,
                    help="stack height in rows (of 20) from which a placed piece counts as 'in danger' (default 16)")
    ap.add_argument("--inject", nargs="*", choices=sorted(INJECTED_AGENTS), default=[],
                    help="warm start: add these earlier-found agents to generation 0 (e.g. --inject g26). "
                         "The seed agents and the baseline weights are always included")
    ap.add_argument("--no-baseline", action="store_true",
                    help="don't play the reference (baseline) agent each generation (saves ~1 agent of compute)")
    return ap.parse_args()


def next_run_name(root):
    os.makedirs(root, exist_ok=True)
    nums = [int(m.group(1)) for d in os.listdir(root)
            if (m := re.fullmatch(r"run_(\d+)", d))]
    return f"run_{max(nums, default=0) + 1}"


def generation_seeds(base_seed, generation, games):
    """Same seeds for every agent in a generation; different seeds every generation."""
    return [base_seed + generation * 10_000 + k for k in range(games)]


def main():
    args = parse_args()
    workers = args.workers or os.cpu_count() or 1

    run_name = args.resume or next_run_name(args.out)
    run_dir = os.path.abspath(os.path.join(args.out, run_name))
    resuming = args.resume is not None
    if resuming and not os.path.isdir(run_dir):
        sys.exit(f"Run folder not found: {run_dir}")
    os.makedirs(run_dir, exist_ok=True)

    agent_log = os.path.join(run_dir, "agent_log.csv")
    ga_log = os.path.join(run_dir, "ga_log.csv")
    baseline_log = os.path.join(run_dir, "baseline_log.csv")
    use_baseline = not args.no_baseline
    config_path = os.path.join(run_dir, "config.json")
    checkpoint = os.path.join(run_dir, "ga_checkpoint.pkl")

    ga = GA(population_size=args.pop, n_weights=N_WEIGHTS,
            log_file="ga_log.csv", checkpoint_file="ga_checkpoint.pkl", misc_dir=run_dir)

    ga.survival_power = args.survival_power
    ga.tetris_power = args.tetris_power
    ga.target_tetris_ratio = args.target_tetris_ratio
    ga.danger_power = args.danger_power

    if resuming and os.path.exists(checkpoint):
        last_gen, history = ga.load_checkpoint()
        start_gen = last_gen + 1
    else:
        ga.initialize_population(seed_weights=SEED_WEIGHTS + [INJECTED_AGENTS[n] for n in args.inject])
        start_gen = 0
        history = []
        with open(agent_log, "w", newline="") as f:
            csv.writer(f).writerow(AGENT_LOG_HEADER)
        with open(ga_log, "w", newline="") as f:
            csv.writer(f).writerow(GA_LOG_HEADER)
        if use_baseline:
            with open(baseline_log, "w", newline="") as f:
                csv.writer(f).writerow(BASELINE_LOG_HEADER)
        with open(config_path, "w") as f:
            json.dump(vars(args), f, indent=2)

    max_pieces = int(args.max_time * 1000 / args.ai_delay)
    print(f"[{run_name}] pop={args.pop} games/agent={args.games} "
          f"budget={args.max_time:g}s @ {args.ai_delay}ms/piece = {max_pieces} pieces "
          f"workers={workers} generations={args.generations} (start at {start_gen})")

    with multiprocessing.Pool(workers) as pool:
        generation = start_gen
        while generation < args.generations:
            params = ga.current_params(generation)
            seeds = generation_seeds(args.seed, generation, args.games)
            print(f"\n===> Generation {generation} | seeds {seeds[0]}..{seeds[-1]} | "
                  f"mutation_rate={params['mutation_rate']:.3f} mutation_scale={params['mutation_scale']:.3f}")
            t0 = time.time()

            # Game slot k uses seeds[k] for EVERY agent (and the baseline), so everyone
            # faces identical piece sequences; the baseline is index `args.pop`.
            jobs = [(i, k, ga.population[i], seeds[k], max_pieces, args.ai_delay, args.danger_height)
                    for i in range(args.pop) for k in range(args.games)]
            if use_baseline:
                jobs += [(args.pop, k, BASELINE_WEIGHTS, seeds[k], max_pieces, args.ai_delay, args.danger_height)
                         for k in range(args.games)]
            results = [[None] * args.games for _ in range(args.pop + (1 if use_baseline else 0))]
            done = 0
            for agent_idx, game_idx, res in pool.imap_unordered(play_job, jobs, chunksize=1):
                results[agent_idx][game_idx] = res
                done += 1
                if done % max(1, len(jobs) // 10) == 0:
                    print(f"    {done}/{len(jobs)} games done ({time.time() - t0:.0f}s)")

            def mean(i, key):
                return float(np.mean([g[key] for g in results[i]]))

            fitness_values = [
                ga.evaluate_agent_fitness([g["score"] for g in results[i]],
                                          [g["pieces"] for g in results[i]],
                                          [g["topped_out"] for g in results[i]],
                                          [g["num_tetris"] for g in results[i]],
                                          [g["danger_share"] for g in results[i]])
                for i in range(args.pop)
            ]
            deaths = [sum(g["topped_out"] for g in results[i]) for i in range(args.pop)]

            # Baseline (reference) agent on this generation's seeds. Not part of selection.
            baseline_fit = None
            if use_baseline:
                b = args.pop
                baseline_fit = ga.evaluate_agent_fitness([g["score"] for g in results[b]],
                                                         [g["pieces"] for g in results[b]],
                                                         [g["topped_out"] for g in results[b]],
                                                         danger=[g["danger_share"] for g in results[b]])
                # (no Tetris-target factor for the baseline: it is the reference the target is measured against,
                #  so RelBest/RelAvg read "agent fitness / the baseline's survival-weighted score")
                with open(baseline_log, "a", newline="") as f:
                    csv.writer(f).writerow([
                        generation, baseline_fit, mean(b, "score"), mean(b, "lines"), mean(b, "pieces"),
                        mean(b, "time_s"), mean(b, "lines_per_sec"),
                        sum(g["topped_out"] for g in results[b]),
                        mean(b, "num_1line"), mean(b, "num_2line"), mean(b, "num_3line"), mean(b, "num_tetris"),
                        mean(b, "peak_height"), mean(b, "danger_share"),
                    ])

            best_idx = int(np.argmax(fitness_values))
            ga_row = [
                generation, best_idx,
                max(fitness_values), float(np.mean(fitness_values)), min(fitness_values),
                float(np.std(fitness_values)),
                mean(best_idx, "score"), mean(best_idx, "lines"), mean(best_idx, "pieces"),
                mean(best_idx, "time_s"), mean(best_idx, "lines_per_sec"), deaths[best_idx],
                mean(best_idx, "num_1line"), mean(best_idx, "num_2line"),
                mean(best_idx, "num_3line"), mean(best_idx, "num_tetris"),
            ] + list(ga.population[best_idx])
            if baseline_fit:    # not None and not 0
                ga_row += [baseline_fit, ga_row[2] / baseline_fit, ga_row[3] / baseline_fit]
            else:
                ga_row += [baseline_fit if baseline_fit is not None else "", "", ""]

            with open(agent_log, "a", newline="") as f:
                w = csv.writer(f)
                for i in range(args.pop):
                    w.writerow(
                        [generation, i, mean(i, "score"), mean(i, "lines"), 1, mean(i, "time_s")]
                        + list(ga.population[i])
                        + [mean(i, "num_1line"), mean(i, "num_2line"), mean(i, "num_3line"), mean(i, "num_tetris")]
                        + [fitness_values[i], mean(i, "pieces"), mean(i, "lines_per_sec"), deaths[i]]
                        + [mean(i, "peak_height"), mean(i, "danger_share")]
                    )
            with open(ga_log, "a", newline="") as f:
                csv.writer(f).writerow(ga_row)

            # Stagnation uses the mean of the top few agents, not the single best:
            # seeds change every generation, so one lucky agent would inflate "best ever".
            top = sorted(fitness_values, reverse=True)[:ga.elite_size]
            ga.check_stagnation(float(np.mean(top)))
            diversity = ga.population_diversity()

            rel = (f" | vs baseline: best {ga_row[-2]:.2f}x avg {ga_row[-1]:.2f}x (baseline {baseline_fit:.0f})"
                   if baseline_fit else "")
            print(f"Gen {generation}: best {ga_row[2]:.0f} avg {ga_row[3]:.0f} worst {ga_row[4]:.0f}{rel} "
                  f"| best agent: lines {ga_row[7]:.0f}, tetrises {ga_row[15]:.1f}, deaths {deaths[best_idx]}/{args.games} "
                  f"| diversity={diversity:.3f} stagnation={ga.stagnation_counter} "
                  f"| {time.time() - t0:.0f}s")

            ga.select_and_breed(fitness_values, generation)
            history.append(fitness_values)
            ga.save_checkpoint(generation, history)
            generation += 1


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
