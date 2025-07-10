import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
import time
import sys
import numpy as np
import csv
import multiprocessing

pygame.init()
pygame.display.set_mode((1, 1))

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../Tetris')))
from main import Main
from genetic_algorithm import GA

# --- CONFIGURATION ---
N_WEIGHTS = 10
GENERATIONS = 50
POP_SIZE = 10
N_TRAYS = 4
TIMEOUT_SECONDS = 360

misc_dir = r"D:\\Tetris-Project\\results\\GA"
os.makedirs(misc_dir, exist_ok=True)
AGENT_LOG_FILE = os.path.join(misc_dir, "agent_log.csv")
GA_LOG_FILE = os.path.join(misc_dir, "ga_log.csv")
CHECKPOINT_FILE = os.path.join(misc_dir, "ga_checkpoint.pkl")

def tray_log_name(prefix, tray):
    return os.path.join(misc_dir, f"{prefix}_tray_{tray}.csv")

AGENT_LOG_HEADER = [
    "Generation", "AgentID", "Score", "Lines", "Level", "Time",
    "W1_AggHeight", "W2_Holes", "W3_Blockades", "W4:Bumpiness", "W5:AlmostFull",
    "W6_FillsWell", "W7:ClearBonus4", "W8:ClearBonus3", "W9:ClearBonus2", "W10:ClearBonus1",
    "Num1Line", "Num2Line", "Num3Line", "NumTetris"
]

GA_LOG_HEADER = [
    "Generation", "BestAgentID", "BestFitness", "AvgFitness", "WorstFitness", "FitnessStd",
    "BestScore", "BestLines", "BestLevel", "BestTime",
    "Num1Line", "Num2Line", "Num3Line", "NumTetris",
    "W1:AggHeight", "W2:Holes", "W3:Blockades", "W4:Bumpiness", "W5:AlmostFull",
    "W6:FillsWell", "W7:ClearBonus4", "W8:ClearBonus3", "W9:ClearBonus2", "W10:ClearBonus1"
]

def run_tray(tray, generation, population, fitness_fn, result_queue):
    import os
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    import pygame
    pygame.init()
    pygame.display.set_mode((1, 1))

    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../Tetris')))
    from main import Main

    print(f"[{time.strftime('%X')}] [TRAY {tray}] Starting for Gen {generation}")
    tray_agent_log_rows = []
    fitness_values = np.zeros(len(population))
    agent_stats = np.zeros((len(population), 8)) # Score, Lines, Level, Time, Num1,2,3,Tetris

    start_times = [time.time()] * len(population)
    games = []
    for i in range(len(population)):
        g = Main()
        g.game.ai.weights = population[i]
        games.append(g)
    done = [False] * len(population)
    all_done = False

    while not all_done:
        all_done = True
        for idx, main in enumerate(games):
            if done[idx]:
                continue
            elapsed = time.time() - start_times[idx]
            if elapsed > TIMEOUT_SECONDS:
                main.game.is_game_over = True
                if main.score.frozen_time is None:
                    main.score.frozen_time = TIMEOUT_SECONDS
                done[idx] = True
                continue
            if not main.game.is_game_over:
                main.game.run()
            else:
                if main.score.frozen_time is None:
                    main.score.frozen_time = int(elapsed)
                done[idx] = True
            if not done[idx]:
                all_done = False

    for idx, main in enumerate(games):
        elapsed = time.time() - start_times[idx]
        if main.score.frozen_time is None:
            main.score.frozen_time = min(int(elapsed), TIMEOUT_SECONDS)
        lines = getattr(main.lines, "lines", 0)
        score = getattr(main.score, "score", 0)
        time_sec = main.score.frozen_time
        num_tetris = getattr(main.game, "num_tetris", 0)

        fitness = fitness_fn(lines, score, time_sec, num_tetris)
        fitness_values[idx] = fitness

        agent_row = [
            generation,
            idx,
            score,
            lines,
            getattr(main.score, "levels", 1),
            time_sec,
        ] + population[idx] + [
            getattr(main.game, "num_1line", 0),
            getattr(main.game, "num_2line", 0),
            getattr(main.game, "num_3line", 0),
            getattr(main.game, "num_tetris", 0),
        ]
        tray_agent_log_rows.append(agent_row)
        agent_stats[idx,0] = score
        agent_stats[idx,1] = lines
        agent_stats[idx,2] = getattr(main.score, "levels", 1)
        agent_stats[idx,3] = time_sec
        agent_stats[idx,4] = getattr(main.game, "num_1line", 0)
        agent_stats[idx,5] = getattr(main.game, "num_2line", 0)
        agent_stats[idx,6] = getattr(main.game, "num_3line", 0)
        agent_stats[idx,7] = getattr(main.game, "num_tetris", 0)

    with open(tray_log_name("agent_log", tray), "a", newline="") as f:
        csv.writer(f).writerows(tray_agent_log_rows)

    best_idx = int(np.argmax(fitness_values))
    best_game_stats = agent_stats[best_idx]
    ga_row = [
        generation, best_idx,
        np.max(fitness_values),
        np.mean(fitness_values),
        np.min(fitness_values),
        np.std(fitness_values),
        best_game_stats[0],
        best_game_stats[1],
        best_game_stats[2],
        best_game_stats[3],
        best_game_stats[4],
        best_game_stats[5],
        best_game_stats[6],
        best_game_stats[7],
    ] + population[best_idx]

    with open(tray_log_name("ga_log", tray), "a", newline="") as f:
        csv.writer(f).writerow(ga_row)

    print(f"[{time.strftime('%X')}] [TRAY {tray}] Finished Gen {generation}")
    result_queue.put((tray, fitness_values.tolist(), agent_stats.tolist()))

if __name__ == '__main__':
    ga = GA(
        population_size=POP_SIZE,
        n_weights=N_WEIGHTS,
        log_file="ga_log.csv",
        checkpoint_file=CHECKPOINT_FILE,
        misc_dir=misc_dir
    )

    if not os.path.exists(CHECKPOINT_FILE):
        ga.population = [ga._random_weights() for _ in range(POP_SIZE)]
        start_gen = 0
        history = []
        with open(AGENT_LOG_FILE, "w", newline="") as f:
            csv.writer(f).writerow([
                "Generation", "AgentID", "AvgScore", "AvgLines", "AvgLevel", "AvgTime"
            ] + [f"W{i+1}" for i in range(10)] + [
                "AvgNum1Line", "AvgNum2Line", "AvgNum3Line", "AvgNumTetris"
            ])
        with open(GA_LOG_FILE, "w", newline="") as f:
            csv.writer(f).writerow(GA_LOG_HEADER)
        for tray in range(N_TRAYS):
            with open(tray_log_name("agent_log", tray), "w", newline="") as f:
                csv.writer(f).writerow(AGENT_LOG_HEADER)
            with open(tray_log_name("ga_log", tray), "w", newline="") as f:
                csv.writer(f).writerow(GA_LOG_HEADER)
    else:
        last_gen, history = ga.load_checkpoint()
        start_gen = last_gen + 1

    generation = start_gen
    while generation < GENERATIONS:
        params = ga.current_params(generation)
        print(f"\n========================")
        print(f"===> [MAIN] Generation {generation} starting...")
        print(f"  (mutation_rate={params['mutation_rate']:.3f}, mutation_scale={params['mutation_scale']:.3f}, "
              f"creep_scale={params['creep_scale']:.3f}, blend_prob={params['blend_prob']:.3f}, "
              f"uniform_chance={params['uniform_chance']:.3f}, creep_chance={params['creep_chance']:.3f})")
        t0 = time.time()
        result_queue = multiprocessing.Queue()
        procs = []
        for tray in range(N_TRAYS):
            p = multiprocessing.Process(
                target=run_tray,
                args=(tray, generation, ga.population, ga.evaluate_agent_fitness, result_queue)
            )
            p.start()
            procs.append(p)

        fitness_matrix = np.zeros((N_TRAYS, POP_SIZE))
        agent_stats_matrix = np.zeros((N_TRAYS, POP_SIZE, 8))
        for _ in range(N_TRAYS):
            tray, fitnesses, stats = result_queue.get()
            fitness_matrix[tray, :] = fitnesses
            agent_stats_matrix[tray, :, :] = stats

        for p in procs:
            p.join()

        elapsed = time.time() - t0
        print(f"[{time.strftime('%X')}] [MAIN] All trays finished for generation {generation} in {elapsed:.2f}s")
        print(f"===> [MAIN] Advancing to next generation {generation+1}\n========================\n")

        aggregate_agent_stats = np.mean(agent_stats_matrix, axis=0)
        fitness_values = np.mean(fitness_matrix, axis=0).tolist()
        best_idx = int(np.argmax(fitness_values))
        avg_stats = aggregate_agent_stats[best_idx]
        ga_row = [
            generation, best_idx,
            np.max(fitness_values),
            np.mean(fitness_values),
            np.min(fitness_values),
            np.std(fitness_values),
            avg_stats[0],  # avg score
            avg_stats[1],  # avg lines
            avg_stats[2],  # avg level
            avg_stats[3],  # avg time
            avg_stats[4],  # avg 1line
            avg_stats[5],  # avg 2line
            avg_stats[6],  # avg 3line
            avg_stats[7],  # avg tetris
        ] + ga.population[best_idx]

        with open(AGENT_LOG_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            for idx in range(POP_SIZE):
                writer.writerow(
                    [generation, idx] +
                    aggregate_agent_stats[idx, 0:4].tolist() +
                    ga.population[idx] +
                    aggregate_agent_stats[idx, 4:8].tolist()
                )

        with open(GA_LOG_FILE, "a", newline="") as f:
            csv.writer(f).writerow(ga_row)

        print(f"Gen {generation+1}: avg {ga_row[3]:.1f} best {ga_row[2]} worst {ga_row[4]} std {ga_row[5]:.2f}")

        ga.select_and_breed(fitness_values, generation)
        history.append(fitness_values)
        ga.save_checkpoint(generation, history)
        generation += 1

    pygame.quit()
