"""
Tetris AI (GA variant) — Phase 7: Dual-Worker Hold + 2-Step Lookahead

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

from evaluator import find_best_move, find_best_move_with_hold


class TetrisAI:
    def __init__(self, game, weights=None, play_pipe=None, hold_pipe=None, **kwargs):
        self.game = game
        self.last_action_time = 0
        self.delay = 130
        self.weights = weights or [1.275, 4.0, 1.2, 0.8, 0.5, 3.0, 20, 5, 2, 0.1]

        self._cached_move = None
        self._cached_piece_id = None

        # ---- Dual-worker pipes (Phase 7) ----
        self._play_pipe = play_pipe      # Worker A: play current
        self._hold_pipe = hold_pipe      # Worker B: hold & play held
        self._piece_id_counter = 0
        self._pending_piece_id = None
        self._last_sent_piece_id = None

        # Store results from each worker
        self._play_result = None
        self._hold_result = None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def update(self, next_shape, held_piece=None, is_held=False):
        if self.game.is_game_over or not self.game.tetromino or not next_shape:
            return

        now = pygame.time.get_ticks()

        tetromino = self.game.tetromino
        shape = tetromino.shape
        current_rot = tetromino.rotation_index
        current_px = int(tetromino.pivot.x)
        piece_id = id(tetromino)

        # ---- ASYNC DUAL-WORKER MODE (Phase 7) ----
        if self._play_pipe is not None:
            self._update_dual_async(
                tetromino, shape, current_rot, current_px,
                piece_id, next_shape,
                held_piece, is_held, now
            )
            return

        # ---- SYNC MODE (fallback — uses hold-aware 1-step) ----
        if now - self.last_action_time < self.delay:
            return

        if piece_id != self._cached_piece_id:
            grid = [
                [1 if self.game.game_data[r][c] else 0 for c in range(COLUMNS)]
                for r in range(ROWS)
            ]
            result = find_best_move_with_hold(
                grid, shape, next_shape, held_piece, is_held, self.weights
            )
            if result is None:
                self._cached_piece_id = piece_id
                self._cached_move = None
                return
            self._cached_move = result    # (rot, x, should_hold)
            self._cached_piece_id = piece_id

        if self._cached_move is None:
            return

        best_rot, best_x, should_hold = self._cached_move

        if should_hold:
            self.game.hold_piece()
            self._cached_piece_id = None
            self._cached_move = None
            return

        self._execute_move(tetromino, best_rot, best_x, current_rot, current_px, now)

    # ------------------------------------------------------------------
    # Dual-worker async mode
    # ------------------------------------------------------------------
    def _update_dual_async(self, tetromino, shape, current_rot, current_px,
                           piece_id, next_shape,
                           held_piece, is_held, now):
        """
        Dual-worker async: send board to BOTH workers simultaneously.
        Worker A = play current piece (1-step lookahead).
        Worker B = hold & play held piece (1-step lookahead).
        """
        # ---- Send to both workers when piece changes ----
        if piece_id != self._last_sent_piece_id:
            self._piece_id_counter += 1
            self._last_sent_piece_id = piece_id
            self._pending_piece_id = self._piece_id_counter
            self._cached_move = None
            self._play_result = None
            self._hold_result = None

            grid_tuple = tuple(
                tuple(1 if self.game.game_data[r][c] else 0 for c in range(COLUMNS))
                for r in range(ROWS)
            )

            # Worker A: play the CURRENT piece
            self._play_pipe.send(
                (self._piece_id_counter, grid_tuple, shape, next_shape)
            )

            # Worker B: hold and play the HELD piece
            if not is_held and self._hold_pipe is not None:
                if held_piece is not None:
                    self._hold_pipe.send(
                        (self._piece_id_counter, grid_tuple, held_piece,
                         next_shape)
                    )
                else:
                    self._hold_pipe.send(
                        (self._piece_id_counter, grid_tuple, next_shape,
                         None)
                    )

        # ---- Poll Worker A (play) ----
        while self._play_pipe.poll():
            recv_id, rot, x, score = self._play_pipe.recv()
            if recv_id == self._pending_piece_id:
                self._play_result = (rot, x, score) if rot is not None else None

        # ---- Poll Worker B (hold) ----
        if self._hold_pipe is not None:
            while self._hold_pipe.poll():
                recv_id, rot, x, score = self._hold_pipe.recv()
                if recv_id == self._pending_piece_id:
                    self._hold_result = (rot, x, score) if rot is not None else None

        # ---- Decide: play or hold? ----
        if self._play_result is None and self._hold_result is None:
            return

        play_score = self._play_result[2] if self._play_result else float("-inf")
        hold_score = self._hold_result[2] if self._hold_result else float("-inf")

        if hold_score > play_score and self._hold_result is not None:
            best_rot, best_x = self._hold_result[0], self._hold_result[1]
            self._cached_move = (best_rot, best_x, True)
        elif self._play_result is not None:
            best_rot, best_x = self._play_result[0], self._play_result[1]
            self._cached_move = (best_rot, best_x, False)
        else:
            return

        # ---- Execute ----
        best_rot, best_x, should_hold = self._cached_move

        if should_hold:
            self.game.hold_piece()
            self._cached_piece_id = None
            self._cached_move = None
            self._play_result = None
            self._hold_result = None
            return

        rot_needed = (best_rot - current_rot) % 4
        dx_needed = best_x - current_px

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
    # Core search (legacy sync)
    # ------------------------------------------------------------------
    def _find_best_move(self, grid, shape, current_rot, next_shape):
        """Delegate move search to shared evaluator with GA weights."""
        return find_best_move(grid, shape, next_shape, self.weights)
