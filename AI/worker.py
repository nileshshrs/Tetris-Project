"""
AI Worker Process — Phase 7: Dual-Worker Hold-Aware

Two workers run in parallel:
  - PLAY worker: evaluates "play current piece" with 1-step lookahead
  - HOLD worker: evaluates "hold & play held piece" with 1-step lookahead

Both return scores so the main process can compare branches.

Protocol:
  Receive: (piece_id, grid_tuple, shape, next_shape)
  Send:    (piece_id, best_rot, best_x, best_score)

Zero Pygame display dependency. Pure integer computation.
"""

import os
import sys

# Ensure AI/ is on the path for evaluator imports.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))
# Ensure Tetris/ is on the path for settings/core imports used by evaluator.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Tetris")))

from evaluator import find_best_move_scored


_DEFAULT_WEIGHTS = [1.275, 4.0, 1.2, 0.8, 0.5, 3.0, 20, 5, 2, 0.1]


def run_ai_worker(pipe, weights=None):
    """
    Generic worker loop. Receives a piece to evaluate, returns best move + score.
    The CALLER decides what piece to send (current or held).

    Protocol:
        Receive: (piece_id, grid_tuple, shape, next_shape)
        Send:    (piece_id, best_rot, best_x, best_score)
    """
    if weights is None:
        weights = _DEFAULT_WEIGHTS

    while True:
        try:
            data = pipe.recv()
            if data is None:
                break    # Shutdown signal

            piece_id, grid_tuple, shape, next_shape = data
            grid = [list(row) for row in grid_tuple]

            result = find_best_move_scored(grid, shape, next_shape, weights)

            if result is None:
                pipe.send((piece_id, None, None, float("-inf")))
            else:
                best_rot, best_x, best_score = result
                pipe.send((piece_id, best_rot, best_x, best_score))

        except EOFError:
            break
        except Exception as e:
            print(f"[AI Worker] Error: {e}")
            import traceback
            traceback.print_exc()
            continue
