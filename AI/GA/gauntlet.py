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
#   'r1a1': np.array([ 8.6343977848961533,  8.1938474750928076,  9.6384945494278913,
#     4.7682521478240343,  0.6135199402618220,  8.8390676265467825,
#     11.7346490519098481, 18.4956904231396138,  1.7212237252132077,
#     3.3244916866697718]),
  'r1a3': np.array([11.9429501277814154, 11.9956569144951484, 13.8195047235532193,
    3.0081030174172518,  2.0364899655567483,  4.9193353835708287,
    8.6121577277877837,  7.5240717007744324, 11.4143736309352644,
    2.0817681429046968]),
  'r5a2': np.array([ 7.9896059740269649, 13.5655022574864557, 15.2890701288809687,
    0.6316295819338924,  0.8882814609937868,  5.8975487332909431,
    8.2717619775902822, 16.0026871594296516,  7.6903405469675716,
    9.7951892000394221]),
#   't1a3': np.array([15.542284669066337, 16.765635983153906, 2.9161714152460676,
#     3.807318124069837, 0.5696669626691833, 6.117714919760799, 
#     4.505426234452847, 6.60584610827727, 6.383616521399759,
#     10.29353896728732]),
#   'm1': np.array([1.275, 4.0, 1.2, 0.8, 0.5, 3.0, 20, 5, 2, 0.1]),
} 

agent_weights_dict = final_run

agent_names = list(agent_weights_dict.keys())
agent_weights_list = [agent_weights_dict[name] for name in agent_names]

N_AGENTS = 2
GAMES_PER_AGENT = 20
TIMEOUT_SECONDS = 600  # 30 seconds per game
misc_dir = r"D:\\Tetris-Project\\results\\gauntlet\\run_7"
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
