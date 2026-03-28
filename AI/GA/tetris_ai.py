"""
Tetris AI (GA variant) — Phase 3 Polish

Same architecture as TetrisAI.py but accepts a GA-tunable weights array.
Zero object instantiation in the search loop. Single-pass board features.

Weight order: [agg_height, holes, blockades, bumpiness, almost_full,
               fills_well, clear_4, clear_3, clear_2, clear_1]
"""

import os
import sys

import pygame
from settings import ROWS, COLUMNS

# Ensure AI/ is importable when run from different entry points.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from evaluator import find_best_move


class TetrisAI:
    def __init__(self, game, weights=None, async_pipe=None):
        self.game = game
        self.last_action_time = 0
        self.delay = 130
        self.weights = weights or [1.2, 4.0, 1.2, 0.8, 0.5, 3.0, 20, 5, 2, 0.1]

        self._cached_move = None
        self._cached_piece_id = None

        # ---- Async mode (Phase 6) ----
        self._async_pipe = async_pipe    # parent_conn from multiprocessing.Pipe
        self._piece_id_counter = 0       # Monotonic piece ID
        self._pending_piece_id = None    # ID of the piece we're waiting on
        self._last_sent_piece_id = None  # ID of current piece we sent to worker

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def update(self, next_shape):
        if self.game.is_game_over or not self.game.tetromino or not next_shape:
            return

        now = pygame.time.get_ticks()

        tetromino = self.game.tetromino
        shape = tetromino.shape
        current_rot = tetromino.rotation_index
        current_px = int(tetromino.pivot.x)
        piece_id = id(tetromino)

        # ---- ASYNC MODE (Phase 6) ----
        if self._async_pipe is not None:
            self._update_async(tetromino, shape, current_rot, current_px,
                               piece_id, next_shape, now)
            return

        if now - self.last_action_time < self.delay:
            return

        if piece_id != self._cached_piece_id:
            grid = [
                [1 if self.game.game_data[r][c] else 0 for c in range(COLUMNS)]
                for r in range(ROWS)
            ]
            result = self._find_best_move(grid, shape, current_rot, next_shape)
            if result is None:
                self._cached_piece_id = piece_id
                self._cached_move = None
                return
            self._cached_move = result
            self._cached_piece_id = piece_id

        if self._cached_move is None:
            return

        best_rot, best_x = self._cached_move
        self._execute_move(tetromino, best_rot, best_x, current_rot, current_px, now)

    def _update_async(self, tetromino, shape, current_rot, current_px,
                      piece_id, next_shape, now):
        """Async update: send state to worker, poll for results."""
        
        # ---- Send new piece state to worker if piece changed ----
        if piece_id != self._last_sent_piece_id:
            self._piece_id_counter += 1
            self._last_sent_piece_id = piece_id
            self._pending_piece_id = self._piece_id_counter
            self._cached_move = None

            # Convert game_data to integer grid as tuple-of-tuples
            grid_tuple = tuple(
                tuple(1 if self.game.game_data[r][c] else 0 for c in range(COLUMNS))
                for r in range(ROWS)
            )
            self._async_pipe.send(
                (self._piece_id_counter, grid_tuple, shape, next_shape)
            )

        # ---- Poll for result (non-blocking) ----
        while self._async_pipe.poll():
            recv_id, best_rot, best_x = self._async_pipe.recv()
            
            # Stale check: discard if piece has changed since we sent
            if recv_id == self._pending_piece_id:
                if best_rot is not None:
                    self._cached_move = (best_rot, best_x)
                else:
                    self._cached_move = None

        # ---- Execute cached move ----
        if self._cached_move is not None:
            best_rot, best_x = self._cached_move
            
            rot_needed = (best_rot - current_rot) % 4
            dx_needed = best_x - current_px
            
            # Only delay the hard drop. Execute shifts and rotations instantly so gravity doesn't ruin the trajectory.
            if rot_needed == 0 and dx_needed == 0:
                if now - self.last_action_time < self.delay:
                    return
                    
            self._execute_move(tetromino, best_rot, best_x, current_rot, current_px, now)

    def _execute_move(self, tetromino, best_rot, best_x, current_rot, current_px, now):
        """Execute a computed move on the real tetromino."""
        rotations_needed = (best_rot - current_rot) % 4
        dx_needed = best_x - current_px

        for _ in range(rotations_needed):
            tetromino.rotate()

        if dx_needed > 0:
            for _ in range(dx_needed):
                tetromino.move_horizontal(+1)
        elif dx_needed < 0:
            for _ in range(-dx_needed):
                tetromino.move_horizontal(-1)

        if rotations_needed == 0 and dx_needed == 0:
            if hasattr(self.game, 'perform_hard_drop'):
                self.game.perform_hard_drop()
            elif hasattr(tetromino, 'hard_drop'):
                tetromino.hard_drop()
            else:
                while tetromino.move_down():
                    pass

        self.last_action_time = now

    # ------------------------------------------------------------------
    # Core search
    # ------------------------------------------------------------------
    def _find_best_move(self, grid, shape, current_rot, next_shape):
        """Delegate move search to shared evaluator with GA weights."""
        return find_best_move(grid, shape, next_shape, self.weights)
