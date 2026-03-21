"""
AI Worker Process — Phase 6: Async Multiprocessing

Runs in a separate OS process. Receives game state via Pipe,
computes best move using TetrisCore, sends result back.

Zero Pygame display dependency. Pure integer computation.
"""

import sys
import os

# Ensure Tetris/ is on the path for settings and core imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Tetris')))

from settings import TETROMINOS, ROWS, COLUMNS
from core import TetrisCore


# ---------------------------------------------------------------------------
# Module-level constants (same as TetrisAI.py)
# ---------------------------------------------------------------------------
_SPAWN_Y = -1
_SPAWN_X = (COLUMNS // 2) - 1


# ---------------------------------------------------------------------------
# Board feature extraction (copied from TetrisAI.py — no Pygame dependency)
# ---------------------------------------------------------------------------
def _compute_board_features(board, virtual_set):
    """Single-pass extraction of all heuristic features."""
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
    """Count cleared lines without grid copy."""
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


# ---------------------------------------------------------------------------
# Move search (headless — no Pygame, no object instantiation)
# ---------------------------------------------------------------------------
def find_best_move(grid, shape, next_shape, weights=None):
    """
    Find the best (rot, x) placement for the given shape on the grid.

    Args:
        grid: 2D list of ints (0 = empty, non-zero = occupied)
        shape: Tetromino key ('T', 'I', etc.)
        next_shape: Next tetromino key for lookahead
        weights: Optional list of 10 floats for GA-tuned weights.
                 If None, uses default hardcoded weights.

    Returns:
        (best_rot, best_x) tuple, or None if no valid placement exists.
    """
    # Default weights (same as TetrisAI.py)
    if weights is None:
        w_agg_height = 1.275
        w_holes = 4.0
        w_blockades = 1.2
        w_bumpiness = 0.8
        w_almost_full = 0.5
        w_fills_well = 3.0
        clear_bonus_map = {4: 20, 3: 5, 2: 2, 1: 0.1}
    else:
        w_agg_height = weights[0]
        w_holes = weights[1]
        w_blockades = weights[2]
        w_bumpiness = weights[3]
        w_almost_full = weights[4]
        w_fills_well = weights[5]
        clear_bonus_map = {4: weights[6], 3: weights[7], 2: weights[8], 1: weights[9]}

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

        # --- Cost function (inlined for worker independence) ---
        (agg_height, holes, blockades, bumpiness, almost_full,
         well_col, well_depth, heights) = _compute_board_features(
            grid, virtual_set
        )

        fills_well = False
        if well_col != -1:
            for vx, vy in virtual_coords:
                if vx == well_col:
                    if vy >= ROWS - 1 or (vy + 1 < ROWS and grid[vy + 1][vx]):
                        fills_well = True
                        break

        clear_bonus = clear_bonus_map.get(lines_cleared, 0)

        cost_now = (
            w_agg_height * agg_height +
            w_holes * holes +
            w_blockades * blockades +
            w_bumpiness * bumpiness -
            w_almost_full * almost_full +
            (w_fills_well if fills_well else 0) -
            clear_bonus
        )

        # --- Lookahead ---
        if next_shape:
            locked_grid = TetrisCore.lock_piece(grid, shape, rot, x, drop_y)
            cleared_grid, _ = TetrisCore.clear_lines(locked_grid)
            next_score = _evaluate_next(cleared_grid, next_shape,
                                        w_agg_height, w_holes, w_blockades,
                                        w_bumpiness, w_almost_full, w_fills_well,
                                        clear_bonus_map)
            total_score = -cost_now + next_score
        else:
            total_score = -cost_now

        if total_score > best_score:
            best_score = total_score
            best_rot = rot
            best_x = x

    if best_score == float("-inf"):
        return None

    return (best_rot, best_x)


def _evaluate_next(grid, shape,
                   w_agg_height, w_holes, w_blockades,
                   w_bumpiness, w_almost_full, w_fills_well,
                   clear_bonus_map):
    """Evaluate best score for next piece (no lookahead)."""
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

        (agg_height, holes, blockades, bumpiness, almost_full,
         well_col, well_depth, heights) = _compute_board_features(
            grid, virtual_set
        )

        fills_well = False
        if well_col != -1:
            for vx, vy in virtual_coords:
                if vx == well_col:
                    if vy >= ROWS - 1 or (vy + 1 < ROWS and grid[vy + 1][vx]):
                        fills_well = True
                        break

        clear_bonus = clear_bonus_map.get(lines_cleared, 0)

        cost = (
            w_agg_height * agg_height +
            w_holes * holes +
            w_blockades * blockades +
            w_bumpiness * bumpiness -
            w_almost_full * almost_full +
            (w_fills_well if fills_well else 0) -
            clear_bonus
        )
        score = -cost
        if score > best_score:
            best_score = score

    return best_score


# ---------------------------------------------------------------------------
# Worker loop — runs in a separate OS process
# ---------------------------------------------------------------------------
def run_ai(pipe, weights=None):
    """
    Worker loop. Receives game state tuples, computes best move, sends back.

    Protocol:
        Receive: (piece_id, grid_tuple, shape, next_shape)
            - grid_tuple: tuple of tuples (immutable, pickle-safe)
            - shape: str ('T', 'I', etc.)
            - next_shape: str or None

        Send:    (piece_id, best_rot, best_x)
            - piece_id: echoed back for stale check
            - best_rot: int (0-3)
            - best_x: int (column)
            - If no valid move: (piece_id, None, None)
    """
    while True:
        try:
            data = pipe.recv()
            if data is None:
                # Shutdown signal
                break

            piece_id, grid_tuple, shape, next_shape = data

            # Convert tuple-of-tuples back to list-of-lists for TetrisCore
            grid = [list(row) for row in grid_tuple]

            result = find_best_move(grid, shape, next_shape, weights)

            if result is None:
                pipe.send((piece_id, None, None))
            else:
                best_rot, best_x = result
                pipe.send((piece_id, best_rot, best_x))

        except EOFError:
            # Pipe closed
            break
        except Exception as e:
            # Log error but don't crash the worker
            print(f"[AI Worker] Error: {e}")
            continue
