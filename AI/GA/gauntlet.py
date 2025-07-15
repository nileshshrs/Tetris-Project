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
# Tetrominos and TetrisAI are already handled by Main/Game for your setup

# --- AGENT WEIGHTS CONFIG ---
agent_weights_dict = {
    'a1': np.array([17.22803223, 15.56255045,  3.69754601,  1.27151497,  2.30047099,
         7.63371241, 14.69788374,  5.21439596, 10.83183428,  5.01119912]),
    'a2': np.array([11.60820347, 18.27102671,  0.57576856,  0.68553726,  1.82614543,
         0.25228197, 15.82208955,  5.9521243 , 14.91480237,  5.15676438]),
    'a3': np.array([16.56826104, 14.12367637,  4.01928941,  1.56849667,  2.46873159,
         8.07812185, 15.37375631,  4.94395842, 13.52158821,  3.5712284 ]),
    'a4': np.array([17.98164765, 18.28232209, 11.34788085,  0.62226497,  1.75790431,
        15.06014193, 16.17697246,  5.87430688, 15.34724469,  5.16201011])
}

agent_names = list(agent_weights_dict.keys())
agent_weights_list = [agent_weights_dict[name] for name in agent_names]

N_AGENTS = 3
GAMES_PER_AGENT = 20
TIMEOUT_SECONDS = 600  # 30 seconds per game
misc_dir = r"D:\\Tetris-Project\\results\\gauntlet"
os.makedirs(misc_dir, exist_ok=True)

def run_agent(agent_name, agent_weights, num_games, timeout_sec):
    import pygame
    pygame.init()
    pygame.display.set_mode((1, 1))

    csv_path = os.path.join(misc_dir, f"results_{agent_name}.csv")
    write_header = not os.path.exists(csv_path) or os.stat(csv_path).st_size == 0
    with open(csv_path, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow([
                "AgentName", "GameNumber", "Score", "NumTetrises", "Num3Line", "Num2Line", "Num1Line", "TimeSurvived", "TotalLinesCleared", "CurrentLevel"
            ])
        for game_num in range(num_games):
            try:
                print(f"[START] Agent {agent_name}, Game {game_num+1}")
                g = Main()
                g.game.ai.weights = agent_weights
                start_time = time.time()
                while not g.game.is_game_over:
                    elapsed = time.time() - start_time
                    if elapsed > timeout_sec:
                        g.game.is_game_over = True
                        break
                    g.game.run()
                time_survived = getattr(g.score, "frozen_time", None)
                if time_survived is None:
                    time_survived = int(time.time() - start_time)
                total_lines = getattr(g.lines, "lines", 0)
                current_level = getattr(g.score, "levels", 1)
                writer.writerow([
                    agent_name,
                    game_num + 1,
                    getattr(g.score, "score", 0),
                    getattr(g.game, "num_tetris", 0),
                    getattr(g.game, "num_3line", 0),
                    getattr(g.game, "num_2line", 0),
                    getattr(g.game, "num_1line", 0),
                    time_survived,
                    total_lines,
                    current_level
                ])
                f.flush()  # Ensure data is written immediately
                print(f"[END]   Agent {agent_name}, Game {game_num+1}")
            except Exception as e:
                print(f"Exception in agent {agent_name}, game {game_num+1}: {e}")
                import traceback
                traceback.print_exc()
                break  # Stop further games for this agent on error


def run_agent_wrapper(args):
    return run_agent(*args)

if __name__ == "__main__":
    jobs = []
    for name, weights in zip(agent_names, agent_weights_list):
        jobs.append((name, weights, GAMES_PER_AGENT, TIMEOUT_SECONDS))
    max_parallel = N_AGENTS

    with multiprocessing.Pool(max_parallel) as pool:
        pool.map(run_agent_wrapper, jobs)

pygame.quit()
