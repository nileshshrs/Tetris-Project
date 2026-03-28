"""
AI Worker Process — Phase 6: Async Multiprocessing

Runs in a separate OS process. Receives game state via Pipe,
computes best move using the shared evaluator, sends result back.

Zero Pygame display dependency. Pure integer computation.
"""

import os
import sys

# Ensure AI/ is on the path for evaluator imports.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))
# Ensure Tetris/ is on the path for settings/core imports used by evaluator.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Tetris")))

from evaluator import find_best_move


_DEFAULT_WEIGHTS = [3.5, 6.0, 1.5, 1.5, 0.8, 1.5, 20, 8, 4, 2]


def run_ai(pipe, weights=None):
    """
    Worker loop. Receives game state tuples, computes best move, sends back.

    Protocol:
        Receive: (piece_id, grid_tuple, shape, next_shape)
        Send:    (piece_id, best_rot, best_x)
    """
    if weights is None:
        weights = _DEFAULT_WEIGHTS

    while True:
        try:
            data = pipe.recv()
            if data is None:
                break

            piece_id, grid_tuple, shape, next_shape = data
            grid = [list(row) for row in grid_tuple]

            result = find_best_move(grid, shape, next_shape, weights)

            if result is None:
                pipe.send((piece_id, None, None))
            else:
                best_rot, best_x = result
                pipe.send((piece_id, best_rot, best_x))

        except EOFError:
            break
        except Exception as e:
            print(f"[AI Worker] Error: {e}")
            continue
