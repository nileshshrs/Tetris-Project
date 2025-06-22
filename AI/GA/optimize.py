import pygame
import time
import sys, os
import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../Tetris')))
from main import Main
from genetic_algorithm import GA  # <-- Your GA class file

# Ensure screenshot directory exists
screenshot_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../AI/assets'))
os.makedirs(screenshot_dir, exist_ok=True)

# Tray settings
BOARD_W, BOARD_H = 10, 20
TRAY_COLS, TRAY_ROWS = 4, 2
POP_SIZE = TRAY_COLS * TRAY_ROWS
MARGIN = 8
WINDOW_W, WINDOW_H = 1600, 900
INFO_PANEL_W = 92

# GA settings
N_WEIGHTS = 10
GENERATIONS = 100

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

# --- Initialize GA ---
ga = GA(
    population_size=POP_SIZE,
    n_weights=N_WEIGHTS,
    elite_size=2,
    mutation_rate=0.15,
    mutation_scale=0.2
)

# Start population (random or load from checkpoint)
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
    # -- 1. Create tray games with weights from GA pop
    games = []
    for i in range(POP_SIZE):
        g = Main()
        g.game.ai.weights = ga.population[i]
        games.append(g)

    fitness = [None] * POP_SIZE

    # --- Draw tray and take START screenshot ---
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
    gen_text = info_font.render(f"Generation: {generation+1}/{GENERATIONS}", True, (0,255,0))
    screen.blit(gen_text, (20, 10))
    pygame.display.flip()
    pygame.image.save(
        screen,
        os.path.join(screenshot_dir, f"tray_gen_{generation:03d}_start.png")
    )

    # -- 2. Tray loop: run all games until all done
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

            # Only run if not game over
            if not main.game.is_game_over:
                main.game.run()
            else:
                # Freeze timer the first time game ends
                if main.score.frozen_time is None:
                    main.score.frozen_time = int(time.time() - main.score.start_time)
                # Set fitness ONCE (if not already set)
                if fitness[idx] is None:
                    fitness[idx] = main.game.current_lines  # Or .current_score
            if not main.game.is_game_over:
                all_done = False

            # Draw board
            scaled_surface = pygame.transform.smoothscale(main.game.surface, (TRAY_BOARD_W, TRAY_BOARD_H))
            screen.blit(scaled_surface, (cell_x, cell_y))
            pygame.draw.rect(screen, (160, 160, 160), (cell_x, cell_y, TRAY_BOARD_W, TRAY_BOARD_H), 2)
            # Draw info panel
            info_panel = pygame.Surface((INFO_PANEL_W, TRAY_BOARD_H))
            draw_info_panel(main, info_panel)
            screen.blit(info_panel, (cell_x + TRAY_BOARD_W, cell_y))
            # Draw GAME OVER
            if main.game.is_game_over:
                go_text = go_font.render("GAME OVER", True, (255,0,0))
                rect = go_text.get_rect(center=(cell_x + TRAY_BOARD_W//2, cell_y + TRAY_BOARD_H//2))
                screen.blit(go_text, rect)

        # Draw generation counter
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

    # -- 3. Breed/evolve new population for next generation
    fitness = [f if f is not None else 0 for f in fitness]

    avg_fit = np.mean(fitness)
    best_fit = np.max(fitness)
    best_idx = np.argmax(fitness)
    worst_fit = np.min(fitness)
    var_fit = np.var(fitness)
    best_weights = ga.population[best_idx]
    history.append({
        "Generation": generation,
        "BestFitness": best_fit,
        "AvgFitness": avg_fit,
        "WorstFitness": worst_fit,
        "FitnessVariance": var_fit,
        "BestWeights": best_weights
    })

    print(f"Gen {generation+1}: avg {avg_fit:.1f} best {best_fit} worst {worst_fit}")

    ga.save_checkpoint(generation, history)
    ga.select_and_breed(fitness)
    generation += 1

pygame.quit()

# Save CSV at the end
df = pd.DataFrame(history)
df.to_csv(ga.log_file, index=False)
print(f"Log saved to {ga.log_file}")
