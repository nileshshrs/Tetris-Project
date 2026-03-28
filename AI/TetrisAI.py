"""
Tetris AI — Phase 3: Quantum AI Refactor

Zero object instantiation in the search loop. All placement evaluation
uses pure integer math via TetrisCore. The only Pygame usage is in
update() for timing (get_ticks) and executing moves on the real piece.

Key changes from Phase 2:
  - Deleted _clone_tetromino — no class instantiation in the hot path
  - Virtual math: raw index-checking on the integer board
  - No-copy heuristics: virtual_coords treated as occupied without grid copy
  - Reachability: vertical scan ensures the AI can actually reach placements
  - All 4 rotation states evaluated (except O = 1)
  - Lookahead uses TetrisCore.lock_piece + clear_lines (with line clearing!)
  - Performance: pre-fetched block coords, module-level constants, batch eval
"""

import os
import sys

import pygame
from Tetris.settings import ROWS, COLUMNS

# Ensure AI/ is importable when run from different entry points.
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from evaluator import find_best_move


# ---------------------------------------------------------------------------
# Main AI class
# ---------------------------------------------------------------------------
class TetrisAI:
    """
    High-speed Tetris AI using pure integer math.

    The search loop never instantiates any class — it works entirely with
    (shape_key, rotation_index, pivot_x, pivot_y) tuples and delegates
    all board logic to TetrisCore static methods.
    """

    def __init__(self, game, async_pipe=None):
        self.game = game
        self.last_action_time = 0
        self.delay = 60

        # ---- Move cache ----
        self._cached_move = None
        self._cached_piece_id = None

        # ---- Async mode (Phase 6) ----
        self._async_pipe = async_pipe    # parent_conn from multiprocessing.Pipe
        self._piece_id_counter = 0       # Monotonic piece ID
        self._pending_piece_id = None    # ID of the piece we're waiting on
        self._last_sent_piece_id = None  # ID of current piece we sent to worker

        # ---- Heuristic weights (EXACT values from pre-refactor) ----
        # DO NOT CHANGE these without re-tuning / GA.
        self._w_agg_height = 1.275
        self._w_holes = 4.0
        self._w_blockades = 1.2
        self._w_bumpiness = 0.8
        self._w_almost_full = 0.5
        self._w_fills_well = 3.0
        self._clear_bonus = {4: 20, 3: 5, 2: 2, 1: 0.1}

    # ------------------------------------------------------------------
    # Public entry point — called once per frame by Game.run()
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

        # ---- SYNC MODE (original, unchanged) ----
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
    # Core search — pure integer, zero Pygame, zero object instantiation
    # ------------------------------------------------------------------
    def _find_best_move(self, grid, shape, current_rot, next_shape):
        """Delegate move search to shared evaluator."""
        weights = [
            self._w_agg_height,
            self._w_holes,
            self._w_blockades,
            self._w_bumpiness,
            self._w_almost_full,
            self._w_fills_well,
            self._clear_bonus.get(4, 0),
            self._clear_bonus.get(3, 0),
            self._clear_bonus.get(2, 0),
            self._clear_bonus.get(1, 0),
        ]
        return find_best_move(grid, shape, next_shape, weights)


# ---------------------------------------------------------------------------
# GA-tuned weight sets (preserved from pre-refactor for reference)
# ---------------------------------------------------------------------------
# best possible weight from GA

w1 = [
    5.144482627321173,
    4.592403558759385,
    0.3629109377693661,
    1.0986703145456884,
    0.4778186644597975,
    0.8234567284825127,
    0.047722264791939265,
    0.14853117878737487,
    3.5644486713487082,
    3.0656886100418195
]
w2 = [
    9.199501774279456,
    11.643503548109585,
    5.129311510706264,
    5.62383445331896,
    2.61919274127448,
    19.790225060345445,
    11.067801299095951,
    13.400649008588255,
    14.562817793884358,
    1.5204907187507872
]

w3 = [
    15.542284669066337,
    16.765635983153906,
    2.9161714152460676,
    3.807318124069837,
    0.5696669626691833,
    6.117714919760799,
    4.505426234452847,
    6.60584610827727,
    6.383616521399759,
    10.29353896728732
]