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
GENERATIONS = 20

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
    "Generation", "AgentID", "Score", "Lines", "Level", "Time",
    "W1_AggHeight", "W2_Holes", "W3_Blockades", "W4_Bumpiness", "W5_AlmostFull",
    "W6_FillsWell", "W7_ClearBonus4", "W8_ClearBonus3", "W9_ClearBonus2", "W10:ClearBonus1",
    "BestFitness", "AvgFitness", "WorstFitness", "FitnessStd",
    "Num1Line", "Num2Line", "Num3Line", "NumTetris"
]

GA_LOG_HEADER = [
    "Generation", "BestAgentID", "BestFitness", "AvgFitness", "WorstFitness", "FitnessStd",
    "Num1Line", "Num2Line", "Num3Line", "NumTetris",
    "W1:AggHeight", "W2:Holes", "W3:Blockades", "W4:Bumpiness", "W5:AlmostFull",
    "W6:FillsWell", "W7:ClearBonus4", "W8:ClearBonus3", "W9:ClearBonus2", "W10:ClearBonus1"
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
    with open(GA_LOG_FILE, "w", newline="") as f:
        csv.writer(f).writerow(GA_LOG_HEADER)

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

    TIMEOUT_SECONDS = 900   # 25 minutes per agent
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

    # --- AGENT LOGGING (write full log every gen) ---
    agent_log_rows = []
    if os.path.exists(AGENT_LOG_FILE):
        df_agent = pd.read_csv(AGENT_LOG_FILE)
        df_agent = df_agent[df_agent["Generation"] < generation]  # keep only old generations
        agent_log_rows = df_agent.values.tolist()

    # Calculate all fitness values and stats
    fitness_values = []
    for idx, main in enumerate(games):
        lines = getattr(main.lines, "lines", 0)
        score = getattr(main.score, "score", 0)
        if hasattr(main.score, "frozen_time") and main.score.frozen_time is not None:
            time_sec = main.score.frozen_time
        else:
            time_sec = int(time.time() - main.score.start_time)
        fitness_val = ga.evaluate_agent_fitness(lines, score, time_sec)
        fitness_values.append(fitness_val)

    fitness_np = np.array(fitness_values)
    best_fitness = np.max(fitness_np)
    avg_fitness = np.mean(fitness_np)
    worst_fitness = np.min(fitness_np)
    fitness_std = np.std(fitness_np)

    for idx, main in enumerate(games):
        agent_row = [
            generation,
            idx,
            getattr(main.score, "score", 0),
            getattr(main.lines, "lines", 0),
            getattr(main.score, "levels", 1),
            None,
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
        num_1line   = getattr(main.game, "num_1line", 0)
        num_2line   = getattr(main.game, "num_2line", 0)
        num_3line   = getattr(main.game, "num_3line", 0)
        num_tetris  = getattr(main.game, "num_tetris", 0)
        agent_row += [best_fitness, avg_fitness, worst_fitness, fitness_std, num_1line, num_2line, num_3line, num_tetris]
        agent_log_rows.append(agent_row)

    # Write full agent log every gen, always including header and all columns
    with open(AGENT_LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(AGENT_LOG_HEADER)
        writer.writerows(agent_log_rows)

    # --- GA LOGGING (write full log every gen, always including header and all columns) ---
    ga_log_rows = []
    if os.path.exists(GA_LOG_FILE):
        df_ga = pd.read_csv(GA_LOG_FILE)
        df_ga = df_ga[df_ga["Generation"] < generation]
        ga_log_rows = df_ga.values.tolist()

    best_idx = int(np.argmax(fitness_np))
    best_agent_game = games[best_idx]
    num_1line   = getattr(best_agent_game.game, "num_1line", 0)
    num_2line   = getattr(best_agent_game.game, "num_2line", 0)
    num_3line   = getattr(best_agent_game.game, "num_3line", 0)
    num_tetris  = getattr(best_agent_game.game, "num_tetris", 0)
    best_weights = ga.population[best_idx]
    ga_row = [
        generation, best_idx, best_fitness, avg_fitness, worst_fitness, fitness_std,
        num_1line, num_2line, num_3line, num_tetris
    ]
    if isinstance(best_weights, np.ndarray):
        best_weights = best_weights.tolist()
    ga_row += best_weights
    ga_log_rows.append(ga_row)

    with open(GA_LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(GA_LOG_HEADER)
        writer.writerows(ga_log_rows)

    print(f"Gen {generation+1}: avg {avg_fitness:.1f} best {best_fitness} worst {worst_fitness} std {fitness_std:.2f}")
    print(f"Log saved to {GA_LOG_FILE}")
    print(f"Agent log saved to {AGENT_LOG_FILE}")

    ga.save_checkpoint(generation, history)  # <-- ADD THIS LINE

    ga.select_and_breed(fitness_values, generation)
    generation += 1
