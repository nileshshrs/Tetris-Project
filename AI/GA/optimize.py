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

# --- LOG FILES ---
AGENT_LOG_FILE = r"D:\Tetris-Project\miscellaneous\agent_log.csv"
GA_LOG_FILE = r"D:\Tetris-Project\miscellaneous\ga_log.csv"
screenshot_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../AI/assets'))
os.makedirs(screenshot_dir, exist_ok=True)

WEIGHT_NAMES = [
    "W1_AggHeight", "W2_Holes", "W3_Blockades", "W4_Bumpiness", "W5_AlmostFull",
    "W6_FillsWell", "W7_ClearBonus4", "W8_ClearBonus3", "W9_ClearBonus2", "W10_ClearBonus1"
]
AGENT_LOG_HEADER = [
    "Generation", "AgentID", "Score", "Lines", "Level", "Time", "Num3LineClears", "NumTetrises"
] + WEIGHT_NAMES

# Write agent log header if not exists
if not os.path.exists(AGENT_LOG_FILE):
    with open(AGENT_LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(AGENT_LOG_HEADER)

# --- PYGAME UI SETUP ---
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

# --- GA ---
ga = GA(
    population_size=POP_SIZE,
    n_weights=N_WEIGHTS,
    elite_size=2,
    mutation_rate=0.15,
    mutation_scale=0.2,
    log_file="ga_log.csv",
    checkpoint_file="ga_checkpoint.pkl",
    misc_dir=r"D:\Tetris-Project\miscellaneous"
)

# --- GA INIT/RESUME ---
if os.path.exists(ga.checkpoint_file):
    print(f"Checkpoint found! Loading from {ga.checkpoint_file}")
    last_gen, history = ga.load_checkpoint()
    start_gen = last_gen + 1
else:
    ga.population = [ga._random_weights() for _ in range(POP_SIZE)]
    start_gen = 0
    history = []

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
    while running and (time.time() - start_time < 30):
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
                break

        screen.fill((20, 20, 20))
        for idx, main in enumerate(games):
            if not main.game.is_game_over:
                main.game.run()  # games advance as normal
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

    pygame.image.save(
        screen,
        os.path.join(screenshot_dir, f"tray_gen_{generation:03d}_start.png")
    )

    # --- Now run the games to completion as usual ---
    clock = pygame.time.Clock()
    all_done = False
    while not all_done and running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False

        screen.fill((20, 20, 20))
        all_done = True
        for idx, main in enumerate(games):
            row = idx // TRAY_COLS
            col = idx % TRAY_COLS
            cell_x = ox0 + col * (TRAY_BOARD_W + INFO_PANEL_W + MARGIN)
            cell_y = oy0 + row * (TRAY_BOARD_H + MARGIN)

            if not main.game.is_game_over:
                main.game.run()
            else:
                if main.score.frozen_time is None:
                    main.score.frozen_time = int(time.time() - main.score.start_time)
                if fitness[idx] is None:
                    fitness[idx] = main.game.current_lines  # Or .current_score
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

    # --- AGENT LOGGING (IMMEDIATE CSV WRITE) ---
    with open(AGENT_LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
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
            writer.writerow(agent_row)

    # --- GENERATION LOGGING ---
    fitness = [f if f is not None else 0 for f in fitness]
    avg_fit = np.mean(fitness)
    best_fit = np.max(fitness)
    best_idx = np.argmax(fitness)
    worst_fit = np.min(fitness)
    std_fit = np.std(fitness)
    best_weights = ga.population[best_idx]
    history.append({
        "Generation": generation,
        "BestFitness": best_fit,
        "AvgFitness": avg_fit,
        "WorstFitness": worst_fit,
        "FitnessStd": std_fit,
        "BestWeights": best_weights
    })

    print(f"Gen {generation+1}: avg {avg_fit:.1f} best {best_fit} worst {worst_fit} std {std_fit:.2f}")

    ga.save_checkpoint(generation, history)
    ga.select_and_breed(fitness)
    generation += 1

pygame.quit()

# Save generation summary (not per-agent, just for reference)
df = pd.DataFrame(history)
df.to_csv(GA_LOG_FILE, index=False, columns=[
    "Generation",
    "BestFitness",
    "AvgFitness",
    "WorstFitness",
    "FitnessStd",
    "BestWeights"
])
print(f"Log saved to {GA_LOG_FILE}")
print(f"Agent log saved to {AGENT_LOG_FILE}")
