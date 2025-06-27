import pygame
import time
import sys, os
import numpy as np
import csv
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../Tetris')))
from main import Main
from genetic_algorithm import GA

# --- CONFIGURATION ---
N_WEIGHTS = 10
GENERATIONS = 100

TRAY_COLS, TRAY_ROWS = 4, 2
POP_SIZE = TRAY_COLS * TRAY_ROWS
MARGIN = 8
WINDOW_W, WINDOW_H = 1600, 900
INFO_PANEL_W = 92

misc_dir = r"D:\Tetris-Project\miscellaneous"
if not os.path.exists(misc_dir):
    os.makedirs(misc_dir, exist_ok=True)

AGENT_LOG_FILE = r"D:\Tetris-Project\miscellaneous\agent_log.csv"
GA_LOG_FILE = r"D:\Tetris-Project\miscellaneous\ga_log.csv"
screenshot_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../AI/assets'))
os.makedirs(screenshot_dir, exist_ok=True)

AGENT_LOG_HEADER = [
    "Generation", "AgentID", "Score", "Lines", "Level", "Time", "Num3LineClears", "NumTetrises",
    "W1_AggHeight", "W2_Holes", "W3_Blockades", "W4_Bumpiness", "W5_AlmostFull",
    "W6_FillsWell", "W7_ClearBonus4", "W8_ClearBonus3", "W9_ClearBonus2", "W10:ClearBonus1"
]

# --- Checkpoint/Resume Handling ---
ga = GA(
    population_size=POP_SIZE,
    n_weights=N_WEIGHTS,
    mutation_rate=0.4,
    mutation_scale=0.5,
    log_file="ga_log.csv",
    checkpoint_file="ga_checkpoint.pkl",
    misc_dir=r"D:\Tetris-Project\miscellaneous"
)

if os.path.exists(ga.checkpoint_file):
    print(f"Checkpoint found! Loading from {ga.checkpoint_file}")
    last_gen, history = ga.load_checkpoint()
    start_gen = last_gen + 1
    print(f"Resuming from generation {start_gen}")
    # Truncate the logs to last completed generation
    if os.path.exists(GA_LOG_FILE):
        df_ga = pd.read_csv(GA_LOG_FILE)
        df_ga = df_ga[df_ga["Generation"] <= last_gen]
        df_ga.to_csv(GA_LOG_FILE, index=False)
    if os.path.exists(AGENT_LOG_FILE):
        df_agent = pd.read_csv(AGENT_LOG_FILE)
        df_agent = df_agent[df_agent["Generation"] <= last_gen]
        df_agent.to_csv(AGENT_LOG_FILE, index=False)
else:
    ga.population = [ga._random_weights() for _ in range(POP_SIZE)]
    start_gen = 0
    history = []
    with open(AGENT_LOG_FILE, "w", newline="") as f:
        csv.writer(f).writerow(AGENT_LOG_HEADER)

pygame.init()
screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
pygame.display.set_caption("Tetris GA Tray")
tray_cell_w = (WINDOW_W - (TRAY_COLS + 1) * MARGIN) // TRAY_COLS
tray_cell_h = (WINDOW_H - (TRAY_ROWS + 1) * MARGIN) // TRAY_ROWS
TRAY_BOARD_W = int(tray_cell_w - INFO_PANEL_W)
TRAY_BOARD_H = tray_cell_h
total_grid_w = TRAY_COLS * (TRAY_BOARD_W + INFO_PANEL_W) + (TRAY_COLS + 1) * MARGIN
total_grid_h = TRAY_ROWS * TRAY_BOARD_H + (TRAY_ROWS + 1) * MARGIN
ox0 = (WINDOW_W - total_grid_w) // 2 + MARGIN
oy0 = (WINDOW_H - total_grid_h) // 2 + MARGIN
info_font = pygame.font.SysFont("arial", 15, bold=True)
go_font = pygame.font.SysFont("arial", 24, bold=True)

def draw_info_panel(main, panel_surface):
    score = getattr(main.score, "score", 0)
    lines = getattr(main.lines, "lines", 0)
    level = getattr(main.score, "levels", 1)
    try:
        if hasattr(main.score, "frozen_time") and main.score.frozen_time is not None:
            seconds = main.score.frozen_time
        else:
            seconds = int(time.time() - main.score.start_time)
        time_str = main.score.format_time(seconds)
    except Exception:
        time_str = "00:00:00"
    next_shapes = getattr(main, "next_shapes", [])
    if isinstance(next_shapes, list):
        next_str = " ".join(next_shapes)
    else:
        next_str = str(next_shapes)
    info_lines = [
        f"Score:", f"{score}",
        f"Lines:", f"{lines}",
        f"Level:", f"{level}",
        f"Time:", f"{time_str}",
        f"Next:", f"{next_str}"
    ]
    panel_surface.fill((24,24,24))
    y = 9
    for line in info_lines:
        panel_surface.blit(info_font.render(line, True, (255,255,255)), (7, y))
        y += 18

generation = start_gen
running = True

while running and generation < GENERATIONS:
    games = []
    for i in range(POP_SIZE):
        g = Main()
        g.game.ai.weights = ga.population[i]
        games.append(g)

    fitness = [None] * POP_SIZE

    # --- Run all games for 30 seconds, then take START screenshot ---
    start_time = time.time()
    clock = pygame.time.Clock()
    force_exit = False
    while running and (time.time() - start_time < 30):
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
                force_exit = True
                break
        if not running or force_exit:
            break

        screen.fill((20, 20, 20))
        for idx, main in enumerate(games):
            if not main.game.is_game_over:
                main.game.run()
            row = idx // TRAY_COLS
            col = idx % TRAY_COLS
            cell_x = ox0 + col * (TRAY_BOARD_W + INFO_PANEL_W + MARGIN)
            cell_y = oy0 + row * (TRAY_BOARD_H + MARGIN)
            scaled_surface = pygame.transform.smoothscale(main.game.surface, (TRAY_BOARD_W, TRAY_BOARD_H))
            screen.blit(scaled_surface, (cell_x, cell_y))
            pygame.draw.rect(screen, (160, 160, 160), (cell_x, cell_y, TRAY_BOARD_W, TRAY_BOARD_H), 2)
            info_panel = pygame.Surface((INFO_PANEL_W, TRAY_BOARD_H))
            draw_info_panel(main, info_panel)
            screen.blit(info_panel, (cell_x + TRAY_BOARD_W, cell_y))
        gen_text = info_font.render(f"Generation: {generation+1}/{GENERATIONS}", True, (0,255,0))
        screen.blit(gen_text, (20, 10))
        pygame.display.flip()
        clock.tick(60)

    if not running or force_exit:
        print(f"\nExiting early: generation {generation} incomplete. No checkpoint/log will be written for this generation.\n")
        break

    pygame.image.save(
        screen,
        os.path.join(screenshot_dir, f"tray_gen_{generation:03d}_start.png")
    )

    # --- Now run the games to completion as usual (with 25-min force kill) ---
    TIMEOUT_SECONDS = 60  # 25 minutes per agent
    agent_start_times = [time.time()] * POP_SIZE

    clock = pygame.time.Clock()
    all_done = False
    force_exit = False
    while not all_done and running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
                force_exit = True
                break
        if not running or force_exit:
            break

        screen.fill((20, 20, 20))
        all_done = True
        for idx, main in enumerate(games):
            row = idx // TRAY_COLS
            col = idx % TRAY_COLS
            cell_x = ox0 + col * (TRAY_BOARD_W + INFO_PANEL_W + MARGIN)
            cell_y = oy0 + row * (TRAY_BOARD_H + MARGIN)

            elapsed = time.time() - agent_start_times[idx]
            if not main.game.is_game_over:
                if elapsed > TIMEOUT_SECONDS:
                    print(f"Agent {idx} killed after timeout ({TIMEOUT_SECONDS} seconds)")
                    main.game.is_game_over = True
                    if hasattr(main.game, "create_new_tetromino"):
                        main.game.create_new_tetromino()
                    main.game.run()
                else:
                    main.game.run()
            else:
                if main.score.frozen_time is None:
                    main.score.frozen_time = int(time.time() - main.score.start_time)
            if not main.game.is_game_over:
                all_done = False

            scaled_surface = pygame.transform.smoothscale(main.game.surface, (TRAY_BOARD_W, TRAY_BOARD_H))
            screen.blit(scaled_surface, (cell_x, cell_y))
            pygame.draw.rect(screen, (160, 160, 160), (cell_x, cell_y, TRAY_BOARD_W, TRAY_BOARD_H), 2)
            info_panel = pygame.Surface((INFO_PANEL_W, TRAY_BOARD_H))
            draw_info_panel(main, info_panel)
            screen.blit(info_panel, (cell_x + TRAY_BOARD_W, cell_y))
            if main.game.is_game_over:
                go_text = go_font.render("GAME OVER", True, (255,0,0))
                rect = go_text.get_rect(center=(cell_x + TRAY_BOARD_W//2, cell_y + TRAY_BOARD_H//2))
                screen.blit(go_text, rect)

        gen_text = info_font.render(f"Generation: {generation+1}/{GENERATIONS}", True, (0,255,0))
        screen.blit(gen_text, (20, 10))
        pygame.display.flip()
        clock.tick(60)

    if not running or force_exit:
        print(f"\nExiting early: generation {generation} incomplete. No checkpoint/log will be written for this generation.\n")
        break

    # --- Draw tray and take END screenshot ---
    screen.fill((20, 20, 20))
    for idx, main in enumerate(games):
        row = idx // TRAY_COLS
        col = idx % TRAY_COLS
        cell_x = ox0 + col * (TRAY_BOARD_W + INFO_PANEL_W + MARGIN)
        cell_y = oy0 + row * (TRAY_BOARD_H + MARGIN)
        scaled_surface = pygame.transform.smoothscale(main.game.surface, (TRAY_BOARD_W, TRAY_BOARD_H))
        screen.blit(scaled_surface, (cell_x, cell_y))
        pygame.draw.rect(screen, (160, 160, 160), (cell_x, cell_y, TRAY_BOARD_W, TRAY_BOARD_H), 2)
        info_panel = pygame.Surface((INFO_PANEL_W, TRAY_BOARD_H))
        draw_info_panel(main, info_panel)
        screen.blit(info_panel, (cell_x + TRAY_BOARD_W, cell_y))
        if main.game.is_game_over:
            go_text = go_font.render("GAME OVER", True, (255,0,0))
            rect = go_text.get_rect(center=(cell_x + TRAY_BOARD_W//2, cell_y + TRAY_BOARD_H//2))
            screen.blit(go_text, rect)
    gen_text = info_font.render(f"Generation: {generation+1}/{GENERATIONS}", True, (0,255,0))
    screen.blit(gen_text, (20, 10))
    pygame.display.flip()
    pygame.image.save(
        screen,
        os.path.join(screenshot_dir, f"tray_gen_{generation:03d}_end.png")
    )

    # --- AGENT LOGGING (always re-write the entire agent log after each gen) ---
    agent_log_rows = []
    if os.path.exists(AGENT_LOG_FILE):
        df_agent = pd.read_csv(AGENT_LOG_FILE)
        df_agent = df_agent[df_agent["Generation"] < generation]  # keep only old generations
        agent_log_rows = df_agent.values.tolist()
    for idx, main in enumerate(games):
        agent_row = [
            generation,
            idx,
            getattr(main.score, "score", 0),
            getattr(main.lines, "lines", 0),
            getattr(main.score, "levels", 1),
            None,
            getattr(main.score, "num_3line_clears", 0),
            getattr(main.score, "num_tetrises", 0)
        ]
        try:
            if hasattr(main.score, "frozen_time") and main.score.frozen_time is not None:
                seconds = main.score.frozen_time
            else:
                seconds = int(time.time() - main.score.start_time)
            agent_row[5] = seconds
        except Exception:
            agent_row[5] = 0
        agent_weights = ga.population[idx]
        for w in agent_weights:
            agent_row.append(w)
        agent_log_rows.append(agent_row)
    # Always rewrite the full agent log file
    with open(AGENT_LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(AGENT_LOG_HEADER)
        writer.writerows(agent_log_rows)

    # --- ENSURE EVERY AGENT'S FITNESS IS ASSIGNED ---
    for idx, main in enumerate(games):
        if fitness[idx] is None:
            lines = getattr(main.lines, "lines", 0)
            score = getattr(main.score, "score", 0)
            if hasattr(main.score, "frozen_time") and main.score.frozen_time is not None:
                time_sec = main.score.frozen_time
            else:
                time_sec = int(time.time() - main.score.start_time)
            fitness[idx] = ga.evaluate_agent_fitness(lines, score, time_sec)
            print(f"[FINAL] Agent {idx}: lines={lines}, score={score}, time={time_sec}, fitness={fitness[idx]}")

    # --- GENERATION LOGGING (history always rewritten by ga.save_log) ---
    avg_fit = np.mean(fitness)
    best_fit = np.max(fitness)
    best_idx = np.argmax(fitness)
    worst_fit = np.min(fitness)
    std_fit = np.std(fitness)
    best_weights = ga.population[best_idx]
    history.append({
        "Generation": generation,
        "BestAgentID": best_idx,
        "BestFitness": best_fit,
        "AvgFitness": avg_fit,
        "WorstFitness": worst_fit,
        "FitnessStd": std_fit,
        "BestWeights": best_weights
    })

    print(f"Gen {generation+1}: avg {avg_fit:.1f} best {best_fit} worst {worst_fit} std {std_fit:.2f}")

    ga.save_checkpoint(generation, history)
    expanded_history = []
    for entry in history:
        row = {
            "Generation": entry["Generation"],
            "BestAgentID": entry["BestAgentID"] if "BestAgentID" in entry else np.nan,
            "BestFitness": entry["BestFitness"],
            "AvgFitness": entry["AvgFitness"],
            "WorstFitness": entry["WorstFitness"],
            "FitnessStd": entry["FitnessStd"],
        }
        weights = entry["BestWeights"]
        if isinstance(weights, np.ndarray):
            weights = weights.tolist()
        row["W1:AggHeight"]    = weights[0]
        row["W2:Holes"]        = weights[1]
        row["W3:Blockades"]    = weights[2]
        row["W4:Bumpiness"]    = weights[3]
        row["W5:AlmostFull"]   = weights[4]
        row["W6:FillsWell"]    = weights[5]
        row["W7:ClearBonus4"]  = weights[6]
        row["W8:ClearBonus3"]  = weights[7]
        row["W9:ClearBonus2"]  = weights[8]
        row["W10:ClearBonus1"] = weights[9]
        expanded_history.append(row)

    cols = [
        "Generation", "BestAgentID", "BestFitness", "AvgFitness", "WorstFitness", "FitnessStd",
        "W1:AggHeight", "W2:Holes", "W3:Blockades", "W4:Bumpiness", "W5:AlmostFull",
        "W6:FillsWell", "W7:ClearBonus4", "W8:ClearBonus3", "W9:ClearBonus2", "W10:ClearBonus1"
    ]
    df = pd.DataFrame(expanded_history)
    df = df[cols]
    df.to_csv(GA_LOG_FILE, index=False)
    print(f"Log saved to {GA_LOG_FILE}")
    print(f"Agent log saved to {AGENT_LOG_FILE}")

    ga.select_and_breed(fitness)
    generation += 1
