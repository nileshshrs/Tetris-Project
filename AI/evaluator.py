"""
Shared Heuristic Evaluator — Zero Pygame Dependency

Single source of truth for board feature extraction and cost function.
Used by TetrisAI.py (in-process), worker.py (subprocess), and
AI/GA/tetris_ai.py (GA variant).

NO PYGAME IMPORTS ALLOWED IN THIS FILE.
"""

import os
import sys

# Ensure Tetris/ is importable (for settings and core)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Tetris")))

from Tetris.settings import COLUMNS, ROWS
from Tetris.core import TetrisCore

# Module-level constants
_SPAWN_Y = -1
_SPAWN_X = (COLUMNS // 2) - 1


def compute_board_features(board, virtual_set):
    """
    Extract all heuristic features in a single pass over the board.

    Returns:
        (agg_height, holes, blockades, bumpiness, almost_full,
         well_col, well_depth, heights)
    """
    heights = [0] * COLUMNS
    holes = 0
    blockades = 0
    almost_full = 0

    # Heights + holes + blockades
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

    # Aggregate height + bumpiness
    agg_height = sum(heights)
    bumpiness = 0
    for i in range(COLUMNS - 1):
        bumpiness += abs(heights[i] - heights[i + 1])

    # Almost-full lines
    for row_idx in range(ROWS):
        empty = 0
        for col in range(COLUMNS):
            if not (board[row_idx][col] or (col, row_idx) in virtual_set):
                empty += 1
                if empty > 2:
                    break
        if 1 <= empty <= 2:
            almost_full += 1

    # Well detection
    max_well_depth = 0
    well_col = -1
    for c in range(COLUMNS):
        left = heights[c - 1] if c > 0 else ROWS
        right = heights[c + 1] if c < COLUMNS - 1 else ROWS
        wd = min(left, right) - heights[c]
        if wd > max_well_depth:
            max_well_depth = wd
            well_col = c

    return (
        agg_height,
        holes,
        blockades,
        bumpiness,
        almost_full,
        well_col,
        max_well_depth,
        heights,
    )


def count_cleared_lines(grid, blocks, pos_x, pos_y, cols=COLUMNS, rows=ROWS):
    """
    Count how many lines would be cleared if piece is placed,
    without copying or mutating the grid.
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


def cost_function(board, virtual_coords, virtual_set, lines_cleared, weights):
    """
    Compute placement cost using shared features.

    weights order:
    [agg_height, holes, blockades, bumpiness, almost_full,
     fills_well, clear_4, clear_3, clear_2, clear_1]
    """
    w = weights

    (
        agg_height,
        holes,
        blockades,
        bumpiness,
        almost_full,
        well_col,
        well_depth,
        heights,
    ) = compute_board_features(board, virtual_set)

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

    # fills_well should reduce cost (reward), not increase it.
    cost = (
        w[0] * agg_height
        + w[1] * holes
        + w[2] * blockades
        + w[3] * bumpiness
        - w[4] * almost_full
        - (w[5] if fills_well else 0)
        - clear_bonus
    )

    return cost


def evaluate_next(grid, shape, weights):
    """Evaluate best score for next piece (no further lookahead)."""
    placements = TetrisCore.evaluate_all_placements(grid, shape, _SPAWN_Y, COLUMNS, ROWS)
    if not placements:
        return float("-inf")

    best_score = float("-inf")

    for rot, x, drop_y, blocks in placements:
        virtual_coords = [(x + bx, drop_y + by) for bx, by in blocks]
        virtual_set = frozenset(virtual_coords)
        lines_cleared = count_cleared_lines(grid, blocks, x, drop_y)
        score = -cost_function(grid, virtual_coords, virtual_set, lines_cleared, weights)
        if score > best_score:
            best_score = score

    return best_score


def find_best_move(grid, shape, next_shape, weights):
    """
    Find the best (rot, x) placement for the given shape on the grid.

    Returns:
        (best_rot, best_x), or None if no valid placement exists.
    """
    placements = TetrisCore.evaluate_all_placements(grid, shape, _SPAWN_Y, COLUMNS, ROWS)
    if not placements:
        return None

    best_score = float("-inf")
    best_rot = 0
    best_x = _SPAWN_X

    for rot, x, drop_y, blocks in placements:
        virtual_coords = [(x + bx, drop_y + by) for bx, by in blocks]
        virtual_set = frozenset(virtual_coords)
        lines_cleared = count_cleared_lines(grid, blocks, x, drop_y)
        cost_now = cost_function(grid, virtual_coords, virtual_set, lines_cleared, weights)

        if next_shape:
            locked_grid = TetrisCore.lock_piece(grid, shape, rot, x, drop_y)
            cleared_grid, _ = TetrisCore.clear_lines(locked_grid)
            next_score = evaluate_next(cleared_grid, next_shape, weights)
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
