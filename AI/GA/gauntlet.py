"""
Gauntlet - benchmark agents on identical seeded games (headless simulator).

Every agent plays the SAME games (game k uses seed base+k for all agents), so
differences between agents come from the weights, not from piece-sequence
luck, and the comparison can be paired. Games run in parallel worker
processes with no Pygame display and no real time; "TimeSurvived" is virtual
game time (pieces * --ai-delay ms), see AI/GA/simulator.py.

The BASELINE agent (the hand-tuned default weights, same as in optimize.py) is
always included and is the reference for the paired comparison in the summary.

Usage:
    python AI/GA/gauntlet.py --from-run run_6         # test the best candidates of a GA run (+ baseline)
    python AI/GA/gauntlet.py --from-run run_6 --top 8 # more candidates
    python AI/GA/gauntlet.py --set agent_weights_5    # a weight set defined below (+ baseline)
    python AI/GA/gauntlet.py                          # the `final_run` set (+ baseline)
    python AI/GA/gauntlet.py --games 5 --max-time 20  # quick test

--from-run takes the rows of results/GA/<run>/ga_log.csv (the best agent of each
generation) with the highest BestFitness, plus the last generation's best. Those scores
come from noisy generations, so this is the step that picks the real winner on fresh seeds.

Results go to results/gauntlet/from_<GA run>/ (e.g. from_run_4) or set_<name>/ (a second
gauntlet on the same source gets a _2 suffix), as results_<agent>.csv with the columns the
notebooks expect (AgentName, GameNumber, Score, NumTetrises, Num3Line, Num2Line,
Num1Line, TimeSurvived, TotalLinesCleared, CurrentLevel), plus Seed, Pieces, Died.
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
from simulator import DANGER_HEIGHT, play_job
from optimize import BASELINE_WEIGHTS   # single source of truth for the baseline agent
from genetic_algorithm import GA        # single source of truth for the Tetris target

BASELINE_NAME = "baseline"

# --- AGENT WEIGHTS CONFIG ---
# GA run 1
agent_weights_1 = {
    'a1': np.array([ 8.6343977848961533,  8.1938474750928076,  9.6384945494278913,
    4.7682521478240343,  0.6135199402618220,  8.8390676265467825,
    11.7346490519098481, 18.4956904231396138,  1.7212237252132077,
    3.3244916866697718]),
    'a2': np.array([ 7.9896059740269649, 13.5655022574864557, 15.2890701288809687,
    0.6316295819338924,  0.8882814609937868,  5.8975487332909431,
    8.2717619775902822, 16.0026871594296516,  7.6903405469675716,
    9.7951892000394221]),
    'a3': np.array([11.9429501277814154, 11.9956569144951484, 13.8195047235532193,
    3.0081030174172518,  2.0364899655567483,  4.9193353835708287,
    8.6121577277877837,  7.5240717007744324, 11.4143736309352644,
    2.0817681429046968]),
}

# GA run 2

agent_weights_2 = {
    'a1': np.array([16.607594519266641, 19.944034254619069, 14.083272141864311,
    8.033603705008725,  6.161773905147342, 13.270945714744132,
    5.291004689101825,  9.963934188563661, 10.930170339838623,
    5.811580419317022]),
    'a2': np.array([14.0441761675998489, 15.1671612532887643, 10.8474522289987405,
    6.9081553888649676,  6.9587918445631631,  7.9852969402642771,
    15.6532548792621142,  3.3538155617527625,  9.7943389993249568,
    1.7495587328052320]),
    'a3': np.array([1.4706543457456362e+01, 1.7824678130159242e+01, 4.9886436671488674e+00,
    7.6017871549520333e+00, 5.6019785668029600e+00, 1.2310614325598497e+01,
    1.1462693823992266e+01, 4.9390542152246031e+00, 7.1151764548764004e-03,
    3.2632641428563218e+00]),
}

# GA run 3

agent_weights_3 = {
    'a1': np.array([18.1153954567132587, 13.2853234631018928,  8.2090105434197760,
    3.9177829887410720,  2.0180893139439569, 10.1106201388668193,
    9.1404323936817793,  6.2591766378328462, 11.3719293984978300,
    0.8244416962213157]),
    'a2': np.array([12.4867438728551043, 11.2714754992413244,  7.7938458117223979,
    4.4722464923568950,  3.5938949653053416, 14.1202742207370768,
    14.8465572502806999, 11.5237690929984353, 10.5261673658042625,
    2.6785074378768572]),
    'a3': np.array([14.5792578260580115, 14.7198438591085736,  7.8168408802843397,
    4.6693852936974984,  2.6512854541110262, 17.6680319127914380,
    15.5584605746655047, 10.7034000776277303, 10.4521110337909722,
    3.4745319643299761]),
}

# GA run 4

agent_weights_4 = {
    'a1': np.array([11.885170064662171, 14.696097422222216,  6.804599035187740,
    3.756388786683533,  4.652478194005265,  5.062160317073977,
    15.595942001306790, 14.282060227055752, 11.456899546158146,
    3.053792694756031]),
    'a2': np.array([14.036647796314201, 17.379740711108209, 14.775196940484438,
    3.451228576586888,  4.599845276769494,  4.715162764049785,
    18.617320453604965, 12.540569250237686, 10.985304381935491,
    5.659028664551329]),
    'a3': np.array([11.354688155338057, 14.581513727678526,  6.975779490945599,
    3.569587803332640,  4.676703075437206,  8.567900328739361,
    15.808726414913236, 14.235239288164902, 11.264206405846457,
    3.037848389015485]),
}

# GA run 5

agent_weights_5 = {
    'a1': np.array([12.2639445183645002, 14.7169502695883274, 10.0149986034930798,
    5.8891938970227438,  3.6794860497947255, 16.5067501101202723,
    5.5040058769723572,  9.0537326691522804,  6.8625717471308381,
    4.4630881429622731]),
    'a2': np.array([13.038744988297422, 11.885484866538864,  7.407738632041696,
    6.986756137066080,  3.376935838936045,  8.041761015816409,
    12.231983826308708, 13.848341055767929,  2.120885059405508,
    5.185449321615649]),
    'a3': np.array([12.374897926108339, 14.683197751087258, 11.841795036604507,
      5.693767555649229,  3.783341363307643, 16.473193254855477,
      5.629110945322520,  8.937794662260542,  6.927479896371951,
      5.838086626258112]),
}


trial_weights = {
    't1a1': np.array([5.144482627321173, 4.592403558759385, 0.3629109377693661,
    1.0986703145456884, 0.4778186644597975, 0.8234567284825127,
    0.047722264791939265, 0.14853117878737487, 3.5644486713487082, 
    3.0656886100418195
    ]),
    't1a2': np.array([9.199501774279456, 11.643503548109585, 5.129311510706264, 
    5.62383445331896, 2.61919274127448, 19.790225060345445,
    11.067801299095951, 13.400649008588255, 14.562817793884358,
    1.5204907187507872
    ]),
    't1a3': np.array([15.542284669066337, 16.765635983153906, 2.9161714152460676,
    3.807318124069837, 0.5696669626691833, 6.117714919760799, 
    4.505426234452847, 6.60584610827727, 6.383616521399759,
    10.29353896728732
    ]),
}

# Example usage:
# print(weights_dict['t1a1'])


# final weight comaparison



final_run = { 
'r1a1': np.array([ 8.6343977848961533,  8.1938474750928076,  9.6384945494278913,
    4.7682521478240343,  0.6135199402618220,  8.8390676265467825,
    11.7346490519098481, 18.4956904231396138,  1.7212237252132077,
    3.3244916866697718]),

't1a3': np.array([15.542284669066337, 16.765635983153906, 2.9161714152460676,
    3.807318124069837, 0.5696669626691833, 6.117714919760799, 
    4.505426234452847, 6.60584610827727, 6.383616521399759,
    10.29353896728732]),
'm1': np.array([1.275, 4.0, 1.2, 0.8, 0.5, 3.0, 20, 5, 2, 0.1]),
}

# Weight sets that can be selected with --set
SETS = {
    "agent_weights_1": agent_weights_1,
    "agent_weights_2": agent_weights_2,
    "agent_weights_3": agent_weights_3,
    "agent_weights_4": agent_weights_4,
    "agent_weights_5": agent_weights_5,
    "trial_weights": trial_weights,
    "final_run": final_run,
}

RESULTS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'results', 'gauntlet')
GA_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'results', 'GA')

CSV_HEADER = [
    "AgentName", "GameNumber", "Score", "NumTetrises", "Num3Line", "Num2Line", "Num1Line",
    "TimeSurvived", "TotalLinesCleared", "CurrentLevel", "Seed", "Pieces", "Died",
    "PeakHeight", "DangerShare",
]

# One row per agent. VsRef* = paired difference in score against the reference agent
# (same seeds), empty for the reference itself.
SUMMARY_HEADER = [
    "AgentName", "IsReference", "Games", "MeanScore", "SemScore", "MedianScore",
    "MeanLines", "MeanTetrises", "Deaths", "VsRefMeanDiff", "VsRefSemDiff", "VsRefBetterIn",
    "SurvivalRate", "TetrisRatio", "MeetsTarget", "MeanPeakHeight", "MeanDangerShare",
]


def meets_target(survival, tetrises, ref_survival, ref_tetrises, ratio, gap):
    """
    The target: survive as often as the reference agent (within `gap`, e.g. 0.05 = one
    death in 20 games) AND make at least `ratio` times its Tetrises per game.
    """
    survives = survival >= ref_survival - gap - 1e-9
    tetris_ok = tetrises >= ratio * ref_tetrises if ref_tetrises > 0 else tetrises > 0
    return bool(survives and tetris_ok)


def parse_args():
    ap = argparse.ArgumentParser(description="Benchmark agents on identical seeded simulator games.")
    ap.add_argument("--set", dest="agent_set", default=None, choices=sorted(SETS),
                    help="which weight set (dict above) to benchmark (default: final_run)")
    ap.add_argument("--from-run", dest="from_run", default=None,
                    help="GA run folder name (e.g. run_6): benchmark its best candidates from ga_log.csv")
    ap.add_argument("--top", type=int, default=5, help="with --from-run: how many top candidates to take")
    ap.add_argument("--ga-out", type=str, default=GA_ROOT, help="folder that holds the GA run_N folders")
    ap.add_argument("--no-baseline", action="store_true",
                    help="don't add the baseline agent (the first agent becomes the reference)")
    ap.add_argument("--target-tetris-ratio", type=float, default=GA.TARGET_TETRIS_RATIO,
                    help="target: an agent must make at least this many times the reference's Tetrises per game "
                         "(default: the same target that is built into the training fitness, GA.TARGET_TETRIS_RATIO = 15)")
    ap.add_argument("--target-survival-gap", type=float, default=0.05,
                    help="target: an agent's survival rate may be at most this far below the reference's "
                         "(0.05 = one death in 20 games; 0 = exactly as often)")
    ap.add_argument("--danger-height", type=int, default=DANGER_HEIGHT,
                    help="stack height in rows from which a placed piece counts as 'in danger' (DangerShare column)")
    ap.add_argument("--games", type=int, default=20, help="games per agent")
    ap.add_argument("--max-time", type=float, default=130.0,
                    help="game-time budget per game in virtual seconds (pieces = max_time / ai_delay)")
    ap.add_argument("--ai-delay", type=int, default=130, help="game time in ms charged per piece")
    ap.add_argument("--seed", type=int, default=1_000_000,
                    help="base seed (kept away from the GA's training seeds)")
    ap.add_argument("--workers", type=int, default=0, help="worker processes (0 = all cores)")
    ap.add_argument("--out", type=str, default=RESULTS_ROOT, help="folder that holds the gauntlet result folders")
    return ap.parse_args()


def next_run_dir(root, label):
    """
    Output folder named after what was tested: from_run_4 (agents of GA run_4) or
    set_final_run (a weight set). A second gauntlet on the same source gets _2, _3, ...
    so nothing is ever overwritten.
    """
    os.makedirs(root, exist_ok=True)
    base = os.path.abspath(os.path.join(root, label))
    path, n = base, 2
    while os.path.exists(path):
        path = f"{base}_{n}"
        n += 1
    os.makedirs(path)
    return path


def candidates_from_run(run_name, top, ga_root):
    """
    Best-of-generation agents from a GA run's ga_log.csv: the `top` rows with the highest
    BestFitness (distinct weights only), plus the last generation's best.
    Returns {name: [10 weights]}.
    """
    path = os.path.abspath(os.path.join(ga_root, run_name, "ga_log.csv"))
    if not os.path.exists(path):
        sys.exit(f"GA log not found: {path}")
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        w_cols = [c for c in reader.fieldnames if re.fullmatch(r"W\d+:.*", c)]
        rows = [r for r in reader if r.get("BestFitness") not in (None, "")]
    if not rows or not w_cols:
        sys.exit(f"No usable rows/weight columns in {path}")

    picked = sorted(rows, key=lambda r: float(r["BestFitness"]), reverse=True)[:top]
    last = max(rows, key=lambda r: int(r["Generation"]))
    if last not in picked:
        picked.append(last)

    agents, seen = {}, set()
    for r in picked:
        w = tuple(round(float(r[c]), 12) for c in w_cols)
        if w in seen:
            continue
        seen.add(w)
        agents[f"{run_name}_g{int(r['Generation'])}"] = list(w)
    return agents


def build_agents(args):
    """Returns (names, weights, reference_index, description)."""
    if args.from_run:
        agents = candidates_from_run(args.from_run, args.top, args.ga_out)
        desc = f"candidates from {args.from_run} (top {args.top} by BestFitness + last generation)"
    else:
        set_name = args.agent_set or "final_run"
        agents = {n: [float(x) for x in w] for n, w in SETS[set_name].items()}
        desc = f"set {set_name}"

    names = list(agents)
    weights = [[float(x) for x in agents[n]] for n in names]

    ref = None
    if not args.no_baseline:
        # If an agent already has the baseline weights (e.g. 'm1' in final_run), it IS the reference.
        for i, w in enumerate(weights):
            if len(w) == len(BASELINE_WEIGHTS) and all(abs(a - b) < 1e-12 for a, b in zip(w, BASELINE_WEIGHTS)):
                ref = i
                break
        if ref is None:
            names.insert(0, BASELINE_NAME)
            weights.insert(0, [float(x) for x in BASELINE_WEIGHTS])
            ref = 0
    else:
        ref = 0
    return names, weights, ref, desc


def main():
    args = parse_args()
    workers = args.workers or os.cpu_count() or 1
    names, weights, ref_idx, desc = build_agents(args)
    max_pieces = int(args.max_time * 1000 / args.ai_delay)
    seeds = [args.seed + k for k in range(args.games)]

    run_dir = next_run_dir(args.out, f"from_{args.from_run}" if args.from_run
                           else f"set_{args.agent_set or 'final_run'}")
    print(f"[gauntlet] {desc} | reference agent: {names[ref_idx]}")
    print(f"[gauntlet] agents={names} games={args.games} "
          f"budget={args.max_time:g}s @ {args.ai_delay}ms/piece = {max_pieces} pieces workers={workers}")
    print(f"[gauntlet] results -> {run_dir}")

    # Record exactly what was tested (weights included), so the run can be reproduced
    # and --from-run candidates can be traced back later.
    with open(os.path.join(run_dir, "config.json"), "w") as f:
        json.dump({
            "args": vars(args),
            "source": desc,
            "reference": names[ref_idx],
            "max_pieces": max_pieces,
            "seeds": seeds,
            "agents": dict(zip(names, weights)),
        }, f, indent=2)

    jobs = [(a, k, weights[a], seeds[k], max_pieces, args.ai_delay, args.danger_height)
            for a in range(len(names)) for k in range(args.games)]
    results = [[None] * args.games for _ in names]

    t0 = time.time()
    done = 0
    with multiprocessing.Pool(workers) as pool:
        for a, k, res in pool.imap_unordered(play_job, jobs, chunksize=1):
            results[a][k] = res
            done += 1
            if done % max(1, len(jobs) // 10) == 0:
                print(f"    {done}/{len(jobs)} games done ({time.time() - t0:.0f}s)")

    for a, name in enumerate(names):
        with open(os.path.join(run_dir, f"results_{name}.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(CSV_HEADER)
            for k, r in enumerate(results[a]):
                w.writerow([name, k + 1, r["score"], r["num_tetris"], r["num_3line"], r["num_2line"],
                            r["num_1line"], round(r["time_s"], 2), r["lines"], 1,
                            seeds[k], r["pieces"], int(r["topped_out"]),
                            r["peak_height"], round(r["danger_share"], 4)])

    # ---- summary ----
    ref = np.array([r["score"] for r in results[ref_idx]], dtype=float)
    width = max(10, max(len(n) for n in names) + 2)
    ref_tet = float(np.mean([r["num_tetris"] for r in results[ref_idx]]))
    ref_surv = 1.0 - sum(r["topped_out"] for r in results[ref_idx]) / args.games
    print(f"\nTarget: survive as often as {names[ref_idx]} ({ref_surv * 100:.0f}%, tolerance "
          f"{args.target_survival_gap * 100:.0f}%) AND make >= {args.target_tetris_ratio:g}x its Tetrises "
          f"({ref_tet:.2f} -> {args.target_tetris_ratio * ref_tet:.2f} per game)")
    print(f"{'agent':<{width}}{'score mean':>12}{'+-sem':>8}{'median':>9}{'lines':>8}{'tetris':>8}"
          f"{'tet/ref':>9}{'survive':>9}{'died':>8}{'target':>8}   vs {names[ref_idx]} (paired, per seed)")
    summary_rows = []
    for a, name in enumerate(names):
        sc = np.array([r["score"] for r in results[a]], dtype=float)
        sem = sc.std(ddof=1) / np.sqrt(len(sc)) if len(sc) > 1 else 0.0
        lines = np.mean([r["lines"] for r in results[a]])
        tet = np.mean([r["num_tetris"] for r in results[a]])
        died = sum(r["topped_out"] for r in results[a])
        surv = 1.0 - died / args.games
        tet_ratio = tet / ref_tet if ref_tet > 0 else None
        if a == ref_idx:
            target = "(ref)"
        else:
            target = "PASS" if meets_target(surv, tet, ref_surv, ref_tet, args.target_tetris_ratio,
                                            args.target_survival_gap) else "fail"
        diff_mean = diff_sem = better = None
        if a == ref_idx or len(sc) < 2:
            paired = "(reference)" if a == ref_idx else "-"
        else:
            d = sc - ref
            diff_mean, diff_sem, better = d.mean(), d.std(ddof=1) / np.sqrt(len(d)), int((d > 0).sum())
            paired = f"{diff_mean:+.0f} +- {diff_sem:.0f}  (better in {better}/{len(d)})"
        ratio_txt = f"{tet_ratio:.1f}x" if tet_ratio is not None else "-"
        print(f"{name:<{width}}{sc.mean():>12.0f}{sem:>8.0f}{np.median(sc):>9.0f}{lines:>8.0f}{tet:>8.1f}"
              f"{ratio_txt:>9}{surv * 100:>8.0f}%{died:>5}/{args.games:<2}{target:>8}   {paired}")
        summary_rows.append([
            name, int(a == ref_idx), len(sc), round(sc.mean(), 2), round(sem, 2), float(np.median(sc)),
            round(float(lines), 2), round(float(tet), 3), died,
            "" if diff_mean is None else round(diff_mean, 2),
            "" if diff_sem is None else round(diff_sem, 2),
            "" if better is None else better,
            round(surv, 3), "" if tet_ratio is None else round(tet_ratio, 3), target,
            round(float(np.mean([r["peak_height"] for r in results[a]])), 2),
            round(float(np.mean([r["danger_share"] for r in results[a]])), 4),
        ])

    with open(os.path.join(run_dir, "summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(SUMMARY_HEADER)
        w.writerows(summary_rows)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
