"""
Tetris AI (GA variant) — Phase 3 Polish

Same architecture as TetrisAI.py but accepts a GA-tunable weights array.
Zero object instantiation in the search loop. Single-pass board features.

Weight order: [agg_height, holes, blockades, bumpiness, almost_full,
               fills_well, clear_4, clear_3, clear_2, clear_1]
"""

import pygame
from settings import TETROMINOS, ROWS, COLUMNS
from core import TetrisCore

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------
_SPAWN_Y = -1
_SPAWN_X = (COLUMNS // 2) - 1


# ---------------------------------------------------------------------------
# Single-pass board feature extraction
# ---------------------------------------------------------------------------
def _compute_board_features(board, virtual_set):
    heights = [0] * COLUMNS
    holes = 0
    blockades = 0
    almost_full = 0

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

    agg_height = sum(heights)
    bumpiness = 0
    for i in range(COLUMNS - 1):
        bumpiness += abs(heights[i] - heights[i + 1])

    for row_idx in range(ROWS):
        empty = 0
        for col in range(COLUMNS):
            if not (board[row_idx][col] or (col, row_idx) in virtual_set):
                empty += 1
                if empty > 2:
                    break
        if 1 <= empty <= 2:
            almost_full += 1

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


def _count_cleared_lines(grid, blocks, pos_x, pos_y,
                         cols=COLUMNS, rows=ROWS):
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


class TetrisAI:
    def __init__(self, game, weights=None):
        self.game = game
        self.last_action_time = 0
        self.delay = 130
        self.weights = weights or [1.2, 4.0, 1.2, 0.8, 0.5, 3.0, 20, 5, 2, 0.1]

        self._cached_move = None
        self._cached_piece_id = None

    # ------------------------------------------------------------------
    # Public entry point
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
        placements = TetrisCore.evaluate_all_placements(
            grid, shape, _SPAWN_Y, COLUMNS, ROWS
        )
        if not placements:
            return None

        best_score = float("-inf")
        best_rot = 0
        best_x = _SPAWN_X

        for rot, x, drop_y, blocks in placements:
            virtual_coords = [(x + bx, drop_y + by) for bx, by in blocks]
            virtual_set = frozenset(virtual_coords)

            lines_cleared = _count_cleared_lines(grid, blocks, x, drop_y)

            cost_now = self._cost_function(grid, virtual_coords, virtual_set,
                                           lines_cleared)

            if next_shape:
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
    # Lookahead — zero grid copies
    # ------------------------------------------------------------------
    def _evaluate_next(self, grid, shape):
        placements = TetrisCore.evaluate_all_placements(
            grid, shape, _SPAWN_Y, COLUMNS, ROWS
        )
        if not placements:
            return float("-inf")

        best_score = float("-inf")

        for rot, x, drop_y, blocks in placements:
            virtual_coords = [(x + bx, drop_y + by) for bx, by in blocks]
            virtual_set = frozenset(virtual_coords)

            lines_cleared = _count_cleared_lines(grid, blocks, x, drop_y)

            score = -self._cost_function(grid, virtual_coords, virtual_set,
                                         lines_cleared)
            if score > best_score:
                best_score = score

        return best_score

    # ------------------------------------------------------------------
    # Heuristic cost function — single-pass, GA weights
    # ------------------------------------------------------------------
    def _cost_function(self, board, virtual_coords, virtual_set,
                       lines_cleared=0):
        w = self.weights

        (agg_height, holes, blockades, bumpiness, almost_full,
         well_col, well_depth, heights) = _compute_board_features(
            board, virtual_set
        )

        fills_well = False
        if well_col != -1:
            for vx, vy in virtual_coords:
                if vx == well_col:
                    if vy >= ROWS - 1 or (vy + 1 < ROWS and board[vy + 1][vx]):
                        fills_well = True
                        break

        if lines_cleared == 4:
            clear_bonus = w[6]
        elif lines_cleared == 3:
            clear_bonus = w[7]
        elif lines_cleared == 2:
            clear_bonus = w[8]
        elif lines_cleared == 1:
            clear_bonus = w[9]
        else:
            clear_bonus = 0

        cost = (
            w[0] * agg_height +
            w[1] * holes +
            w[2] * blockades +
            w[3] * bumpiness -
            w[4] * almost_full +
            (w[5] if fills_well else 0) -
            clear_bonus
        )
        return cost
