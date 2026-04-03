"""
Tetris AI — Phase 7: Dual-Worker Hold + 2-Step Lookahead

Zero object instantiation in the search loop. All placement evaluation
uses pure integer math via TetrisCore. The only Pygame usage is in
update() for timing (get_ticks) and executing moves on the real piece.

Key changes from Phase 6:
  - Dual-worker architecture: Worker A = play current, Worker B = hold & play held
  - 2-step lookahead: current → next → next-next
  - Hold decision: compares play vs. hold branch scores, picks higher
  - SYNC fallback with hold awareness (no external workers needed)
"""

import os
import sys

import pygame
from Tetris.settings import ROWS, COLUMNS

# Ensure AI/ is importable when run from different entry points.
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from evaluator import find_best_move, find_best_move_with_hold


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

    def __init__(self, game, play_pipe=None, hold_pipe=None, **kwargs):
        self.game = game
        self.last_action_time = 0
        self.delay = 60

        # ---- Move cache ----
        self._cached_move = None
        self._cached_piece_id = None

        # ---- Dual-worker pipes (Phase 7) ----
        self._play_pipe = play_pipe      # Worker A: play current
        self._hold_pipe = hold_pipe      # Worker B: hold & play held
        self._piece_id_counter = 0
        self._pending_piece_id = None
        self._last_sent_piece_id = None

        # Store results from each worker
        self._play_result = None         # (rot, x, score) from Worker A
        self._hold_result = None         # (rot, x, score) from Worker B

        # ---- Heuristic weights (proven working values) ----
        # These are the original weights that produced good AI play.
        # After the Phase 3 fills_well sign fix, w[5]=3.0 now correctly
        # REWARDS well-filling (was accidentally penalizing before).
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
            weights = self._get_weights()
            result = find_best_move_with_hold(
                grid, shape, next_shape, held_piece, is_held, weights
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
            self._cached_piece_id = None     # Force re-evaluation after hold
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
        Dual-worker async: send current board to BOTH workers simultaneously.
        Worker A evaluates "play current piece" with 1-step lookahead.
        Worker B evaluates "hold & play held piece" with 1-step lookahead.
        Main process picks whichever branch scores higher.
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

            # Worker A: evaluate playing the CURRENT piece
            self._play_pipe.send(
                (self._piece_id_counter, grid_tuple, shape, next_shape)
            )

            # Worker B: evaluate holding and playing the HELD piece
            # Only send if hold is available this turn
            if not is_held and self._hold_pipe is not None:
                if held_piece is not None:
                    # Swap: play held_piece, lookahead with next_shape
                    self._hold_pipe.send(
                        (self._piece_id_counter, grid_tuple, held_piece,
                         next_shape)
                    )
                else:
                    # First hold ever: play next_shape, no lookahead piece known
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
        # Wait until at least Worker A has responded
        if self._play_result is None and self._hold_result is None:
            return    # Still waiting

        play_score = self._play_result[2] if self._play_result else float("-inf")
        hold_score = self._hold_result[2] if self._hold_result else float("-inf")

        if hold_score > play_score and self._hold_result is not None:
            # Hold is better — swap and re-evaluate will happen next frame
            best_rot, best_x = self._hold_result[0], self._hold_result[1]
            self._cached_move = (best_rot, best_x, True)    # should_hold = True
        elif self._play_result is not None:
            best_rot, best_x = self._play_result[0], self._play_result[1]
            self._cached_move = (best_rot, best_x, False)   # should_hold = False
        else:
            return

        # ---- Execute ----
        best_rot, best_x, should_hold = self._cached_move

        if should_hold:
            self.game.hold_piece()
            self._cached_piece_id = None     # Force re-evaluation after hold
            self._cached_move = None
            self._play_result = None
            self._hold_result = None
            return

        rot_needed = (best_rot - current_rot) % 4
        dx_needed = best_x - current_px

        # Only delay the hard drop (same as before)
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
    # Helpers
    # ------------------------------------------------------------------
    def _get_weights(self):
        """Build weights list from instance attributes."""
        return [
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

    def _find_best_move(self, grid, shape, current_rot, next_shape):
        """Delegate move search to shared evaluator (legacy)."""
        return find_best_move(grid, shape, next_shape, self._get_weights())


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