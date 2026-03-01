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

import pygame
from settings import TETROMINOS, ROWS, COLUMNS
from core import TetrisCore

# ---------------------------------------------------------------------------
# Module-level constants — avoid recomputing per call
# ---------------------------------------------------------------------------
_SPAWN_Y = -1  # Matches BLOCK_OFFSET.y in settings.py
_SPAWN_X = (COLUMNS // 2) - 1  # Matches BLOCK_OFFSET.x in settings.py


# ---------------------------------------------------------------------------
# Single-pass board feature extraction (replaces 4 separate scans)
# ---------------------------------------------------------------------------
def _compute_board_features(board, virtual_set):
    """
    Extract ALL heuristic features in a single pass over the board.

    Returns:
        (agg_height, holes, blockades, bumpiness, almost_full,
         well_col, well_depth, heights)
    """
    heights = [0] * COLUMNS
    holes = 0
    blockades = 0
    almost_full = 0

    # ---- Single column pass: heights + holes + blockades ----
    for col in range(COLUMNS):
        block_found = False
        found_hole = False
        for row in range(ROWS):
            occupied = board[row][col] != 0 or (col, row) in virtual_set
            if occupied:
                if not block_found:
                    heights[col] = ROWS - row
                    block_found = True
                if found_hole:
                    blockades += 1
            else:
                if block_found:
                    holes += 1
                found_hole = True

    # ---- Aggregate height + bumpiness (from heights array) ----
    agg_height = sum(heights)
    bumpiness = 0
    for i in range(COLUMNS - 1):
        bumpiness += abs(heights[i] - heights[i + 1])

    # ---- Almost-full lines (row pass) ----
    for row_idx in range(ROWS):
        empty = 0
        for col in range(COLUMNS):
            if not (board[row_idx][col] or (col, row_idx) in virtual_set):
                empty += 1
                if empty > 2:
                    break
        if 1 <= empty <= 2:
            almost_full += 1

    # ---- Well detection (from heights array) ----
    max_well_depth = 0
    well_col = -1
    for c in range(COLUMNS):
        left = heights[c - 1] if c > 0 else ROWS
        right = heights[c + 1] if c < COLUMNS - 1 else ROWS
        wd = min(left, right) - heights[c]
        if wd > max_well_depth:
            max_well_depth = wd
            well_col = c

    return (agg_height, holes, blockades, bumpiness, almost_full,
            well_col, max_well_depth, heights)


# ---------------------------------------------------------------------------
# Fast line-clear count without grid copy
# ---------------------------------------------------------------------------
def _count_cleared_lines(grid, blocks, pos_x, pos_y,
                         cols=COLUMNS, rows=ROWS):
    """
    Count how many lines would be cleared if piece is placed,
    WITHOUT copying or mutating the grid.

    Checks only the rows touched by the piece.
    """
    touched_rows = set()
    for bx, by in blocks:
        cy = pos_y + by
        if 0 <= cy < rows:
            touched_rows.add(cy)

    count = 0
    for ry in touched_rows:
        full = True
        for cx in range(cols):
            cell_occupied = grid[ry][cx] != 0
            if not cell_occupied:
                # Check if one of the piece blocks fills this cell
                found = False
                for bx, by in blocks:
                    if pos_x + bx == cx and pos_y + by == ry:
                        found = True
                        break
                if not found:
                    full = False
                    break
        if full:
            count += 1
    return count


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

    def __init__(self, game):
        self.game = game
        self.last_action_time = 0
        self.delay = 60

        # ---- Move cache: compute once per piece, not every frame ----
        self._cached_move = None       # (best_rot, best_x)
        self._cached_piece_id = None   # id(tetromino) — changes on new spawn

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
        if now - self.last_action_time < self.delay:
            return

        tetromino = self.game.tetromino
        shape = tetromino.shape
        current_rot = tetromino.rotation_index
        current_px = int(tetromino.pivot.x)
        piece_id = id(tetromino)

        # ---- Use cached move if still the same piece -----------------
        if piece_id != self._cached_piece_id:
            # New piece — compute best move ONCE
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

        # ---- Translate absolute target to relative actions -----------
        rotations_needed = (best_rot - current_rot) % 4
        # After rotating, the pivot X stays the same (SRS pivot system),
        # so dx is simply the difference between target X and current X.
        dx_needed = best_x - current_px

        # ---- Execute on the real tetromino ---------------------------
        for _ in range(rotations_needed):
            tetromino.rotate()

        if dx_needed > 0:
            for _ in range(dx_needed):
                tetromino.move_horizontal(+1)
        elif dx_needed < 0:
            for _ in range(-dx_needed):
                tetromino.move_horizontal(-1)

        # Hard drop when the piece is already in position
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
        """
        Evaluate every reachable placement and return (best_rot, best_x).

        Uses TetrisCore.evaluate_all_placements() for batch generation,
        then scores each with the single-pass heuristic and 1-piece lookahead.
        """
        placements = TetrisCore.evaluate_all_placements(
            grid, shape, _SPAWN_Y, COLUMNS, ROWS
        )
        if not placements:
            return None

        best_score = float("-inf")
        best_rot = 0
        best_x = _SPAWN_X

        for rot, x, drop_y, blocks in placements:
            # Virtual coordinates of the landed piece
            virtual_coords = [
                (x + bx, drop_y + by) for bx, by in blocks
            ]
            virtual_set = frozenset(virtual_coords)

            # Count lines cleared without copying the grid
            lines_cleared = _count_cleared_lines(grid, blocks, x, drop_y)

            cost_now = self._cost_function(grid, virtual_coords, virtual_set,
                                           lines_cleared)

            # 1-piece lookahead on the cleared grid
            if next_shape:
                # Need actual grid with piece locked + lines cleared for lookahead
                locked_grid = TetrisCore.lock_piece(grid, shape, rot, x, drop_y)
                cleared_grid, _ = TetrisCore.clear_lines(locked_grid)
                next_score = self._evaluate_next(cleared_grid, next_shape)
                total_score = -cost_now + next_score
            else:
                total_score = -cost_now

            if total_score > best_score:
                best_score = total_score
                best_rot = rot
                best_x = x

        if best_score == float("-inf"):
            return None

        return best_rot, best_x

    # ------------------------------------------------------------------
    # Lookahead evaluation — mutable ops, zero grid copies
    # ------------------------------------------------------------------
    def _evaluate_next(self, grid, shape):
        """
        Evaluate the best possible score for `shape` on `grid`.
        Uses no-copy virtual coords for speed.
        """
        placements = TetrisCore.evaluate_all_placements(
            grid, shape, _SPAWN_Y, COLUMNS, ROWS
        )
        if not placements:
            return float("-inf")

        best_score = float("-inf")

        for rot, x, drop_y, blocks in placements:
            virtual_coords = [
                (x + bx, drop_y + by) for bx, by in blocks
            ]
            virtual_set = frozenset(virtual_coords)

            # Count cleared lines without copying
            lines_cleared = _count_cleared_lines(grid, blocks, x, drop_y)

            score = -self._cost_function(grid, virtual_coords, virtual_set,
                                         lines_cleared)
            if score > best_score:
                best_score = score

        return best_score

    # ------------------------------------------------------------------
    # Heuristic cost function — single-pass, NO grid copy
    # ------------------------------------------------------------------
    def _cost_function(self, board, virtual_coords, virtual_set,
                       lines_cleared=0):
        """
        Compute placement cost in a single pass over the board.
        """
        # ---- Single-pass feature extraction ----
        (agg_height, holes, blockades, bumpiness, almost_full,
         well_col, well_depth, heights) = _compute_board_features(
            board, virtual_set
        )

        # ---- fills_well check ----
        fills_well = False
        if well_col != -1:
            for vx, vy in virtual_coords:
                if vx == well_col:
                    if vy >= ROWS - 1 or (vy + 1 < ROWS and board[vy + 1][vx]):
                        fills_well = True
                        break

        # ---- Clear bonus (exact same tiers) ----
        clear_bonus = self._clear_bonus.get(lines_cleared, 0)

        # ---- Weighted cost (EXACT pre-refactor formula) ----
        cost = (
            self._w_agg_height * agg_height +
            self._w_holes * holes +
            self._w_blockades * blockades +
            self._w_bumpiness * bumpiness -
            self._w_almost_full * almost_full +
            (self._w_fills_well if fills_well else 0) -
            clear_bonus
        )
        return cost


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