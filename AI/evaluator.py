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

from Tetris.settings import COLUMNS, ROWS, TETROMINOS
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
    # Blockades = filled cells that sit above a hole in the same column
    # (i.e. cells you must remove before you can reach the lowest hole).
    for col in range(COLUMNS):
        block_found = False
        filled_above = 0        # filled cells seen so far in this column
        covering = 0            # filled cells above the lowest hole seen so far
        for row in range(ROWS):
            occupied = board[row][col] != 0 or (col, row) in virtual_set
            if occupied:
                if not block_found:
                    heights[col] = ROWS - row
                    block_found = True
                filled_above += 1
            elif block_found:
                holes += 1
                covering = filled_above
        blockades += covering

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
        _well_depth,    # computed by compute_board_features but not part of the cost
        _heights,
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
    1-step lookahead.

    Returns:
        (best_rot, best_x), or None if no valid placement exists.
    """
    result = find_best_move_scored(grid, shape, next_shape, weights)
    if result is None:
        return None
    return result[0], result[1]


def find_best_move_scored_reference(grid, shape, next_shape, weights):
    """
    REFERENCE implementation (slow, cell-by-cell). Kept as the ground truth that the
    fast search below is verified against; nothing in the game calls it directly.

    Returns:
        (best_rot, best_x, best_score) or None
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

    return (best_rot, best_x, best_score)


# ---------------------------------------------------------------------------
# Fast search (bit-board)
#
# Gives EXACTLY the same moves and scores as the reference implementation above
# (same placements in the same order, same features, same cost expression, same
# tie-breaking) - it is only much cheaper per placement:
#   * every board row is one int (bit c = column c occupied) and every column is one
#     int (bit r = row r occupied), so per-column features (height, holes, blockades)
#     are a few bit operations instead of a scan over 200 cells;
#   * a placement only changes the <= 4 columns / rows the piece touches, so only those
#     are recomputed;
#   * the landing row comes straight from the column heights instead of dropping the
#     piece one row at a time.
# When the stack reaches the spawn rows (almost game over) it falls back to the
# reference placement routine, so edge cases behave identically.
# ---------------------------------------------------------------------------

_popcount = int.bit_count if hasattr(int, "bit_count") else (lambda v: bin(v).count("1"))
_FULL_ROW = (1 << COLUMNS) - 1
_ALL_ROWS = (1 << ROWS) - 1
_NEG_INF = float("-inf")

# shape -> [(rot, blocks, x_lo, x_hi, min_by), ...] in the same order as
# TetrisCore.evaluate_all_placements (rotation-major, x ascending)
_SHAPES = {}
for _name, _data in TETROMINOS.items():
    _rots = _data['rotations']
    _entries = []
    for _rot in range(1 if _name == 'O' else 4):
        _blocks = _rots[_rot]
        _entries.append((
            _rot,
            _blocks,
            -min(bx for bx, _ in _blocks),
            (COLUMNS - 1) - max(bx for bx, _ in _blocks),
            min(by for _, by in _blocks),
        ))
    _SHAPES[_name] = _entries


def _col_stats(cb):
    """(height, holes, blockades) of one column given its bitmask (bit r = row r occupied)."""
    if cb == 0:
        return 0, 0, 0
    low = cb & -cb                        # top-most block = lowest set bit
    height = ROWS - (low.bit_length() - 1)
    holes = height - _popcount(cb)        # empty cells below the top block
    if holes:
        empty_below = ~cb & _ALL_ROWS & ~((low << 1) - 1)
        lowest_hole = empty_below.bit_length() - 1
        blockades = _popcount(cb & ((1 << lowest_hole) - 1))   # filled cells above the lowest hole
    else:
        blockades = 0
    return height, holes, blockades


def _build_state(rows, cb):
    hh = [0] * COLUMNS
    hl = [0] * COLUMNS
    bk = [0] * COLUMNS
    for c in range(COLUMNS):
        hh[c], hl[c], bk[c] = _col_stats(cb[c])
    af = [1 if 1 <= COLUMNS - _popcount(m) <= 2 else 0 for m in rows]
    return (rows, cb, hh, hl, bk, af, sum(hh), sum(hl), sum(bk), sum(af))


def _state_from_rows(rows):
    cb = [0] * COLUMNS
    for r in range(ROWS):
        m = rows[r]
        if m:
            bit = 1 << r
            for c in range(COLUMNS):
                if (m >> c) & 1:
                    cb[c] |= bit
    return _build_state(rows, cb)


def _state_from_grid(grid):
    rows = [0] * ROWS
    cb = [0] * COLUMNS
    for r in range(ROWS):
        row = grid[r]
        m = 0
        bit = 1 << r
        for c in range(COLUMNS):
            if row[c]:
                m |= 1 << c
                cb[c] |= bit
        rows[r] = m
    return _build_state(rows, cb)


def _grid_from_rows(rows):
    return [[(m >> c) & 1 for c in range(COLUMNS)] for m in rows]


def _gen_placements(state, shape):
    """Same list as TetrisCore.evaluate_all_placements(grid, shape, _SPAWN_Y, ...)."""
    hh = state[2]
    if max(hh) >= ROWS - 1:
        # The stack reaches the spawn rows: use the exact reference routine.
        return TetrisCore.evaluate_all_placements(
            _grid_from_rows(state[0]), shape, _SPAWN_Y, COLUMNS, ROWS)

    # Rows 0 and 1 are empty everywhere, so every spawn position is valid and a piece
    # dropped straight down stops at the first block it meets in any of its columns.
    tops = [ROWS - h for h in hh]
    out = []
    for rot, blocks, x_lo, x_hi, min_by in _SHAPES[shape]:
        for x in range(x_lo, x_hi + 1):
            d = ROWS
            for bx, by in blocks:
                v = tops[x + bx] - 1 - by
                if v < d:
                    d = v
            if d + min_by < 0:           # part of the piece would stay above the board
                continue
            out.append((rot, x, d, blocks))
    return out


def _place(state, blocks, x, d, w, need_state):
    """
    Cost of placing `blocks` at column x, landing row d (same value as cost_function),
    plus - if need_state - the state of the board after the piece locks and full rows clear.
    """
    rows, cb, hh, hl, bk, af, _t_h, t_hl, t_bk, t_af = state

    col_add = {}
    row_add = {}
    for bx, by in blocks:
        cx = x + bx
        cy = d + by
        col_add[cx] = col_add.get(cx, 0) | (1 << cy)
        row_add[cy] = row_add.get(cy, 0) | (1 << cx)

    # columns the piece touches
    heights = hh[:]
    holes = t_hl
    blockades = t_bk
    new_cols = {}
    for cx, bits in col_add.items():
        ncb = cb[cx] | bits
        h, ho, bl = _col_stats(ncb)
        heights[cx] = h
        holes += ho - hl[cx]
        blockades += bl - bk[cx]
        new_cols[cx] = (ncb, ho, bl)

    # rows the piece touches
    almost_full = t_af
    lines_cleared = 0
    new_rows = {}
    for ry, bits in row_add.items():
        nm = rows[ry] | bits
        new_rows[ry] = nm
        almost_full += (1 if 1 <= COLUMNS - _popcount(nm) <= 2 else 0) - af[ry]
        if nm == _FULL_ROW:
            lines_cleared += 1

    agg_height = sum(heights)
    bumpiness = 0
    for i in range(COLUMNS - 1):
        diff = heights[i] - heights[i + 1]
        bumpiness += diff if diff >= 0 else -diff

    # deepest well (first column with the maximum depth)
    max_well_depth = 0
    well_col = -1
    for c in range(COLUMNS):
        left = heights[c - 1] if c > 0 else ROWS
        right = heights[c + 1] if c < COLUMNS - 1 else ROWS
        wd = (left if left < right else right) - heights[c]
        if wd > max_well_depth:
            max_well_depth = wd
            well_col = c

    fills_well = False
    if well_col != -1:
        for bx, by in blocks:
            if x + bx == well_col:
                vy = d + by
                if vy >= ROWS - 1 or (rows[vy + 1] >> well_col) & 1:
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

    # identical expression (and evaluation order) to cost_function
    cost = (
        w[0] * agg_height
        + w[1] * holes
        + w[2] * blockades
        + w[3] * bumpiness
        - w[4] * almost_full
        - (w[5] if fills_well else 0)
        - clear_bonus
    )

    if not need_state:
        return cost, None

    n_rows = rows[:]
    for ry, nm in new_rows.items():
        n_rows[ry] = nm
    if lines_cleared:
        kept = [m for m in n_rows if m != _FULL_ROW]
        return cost, _state_from_rows([0] * (ROWS - len(kept)) + kept)

    n_cb = cb[:]
    n_hl = hl[:]
    n_bk = bk[:]
    for cx, (ncb, ho, bl) in new_cols.items():
        n_cb[cx] = ncb
        n_hl[cx] = ho
        n_bk[cx] = bl
    n_af = af[:]
    for ry, nm in new_rows.items():
        n_af[ry] = 1 if 1 <= COLUMNS - _popcount(nm) <= 2 else 0
    return cost, (n_rows, n_cb, heights, n_hl, n_bk, n_af, agg_height, holes, blockades, almost_full)


def _best_next_score(state, shape, w):
    """Fast equivalent of evaluate_next."""
    best = _NEG_INF
    for _rot, x, d, blocks in _gen_placements(state, shape):
        score = -_place(state, blocks, x, d, w, False)[0]
        if score > best:
            best = score
    return best


def find_best_move_scored(grid, shape, next_shape, weights):
    """
    Best (rot, x) placement for `shape` with 1-step lookahead, plus its total score.
    Used by the dual-worker system to compare the play and hold branches.

    Returns:
        (best_rot, best_x, best_score) or None
    """
    state = _state_from_grid(grid)
    placements = _gen_placements(state, shape)
    if not placements:
        return None

    best_score = _NEG_INF
    best_rot = 0
    best_x = _SPAWN_X

    for rot, x, d, blocks in placements:
        if next_shape:
            cost_now, next_state = _place(state, blocks, x, d, weights, True)
            total_score = -cost_now + _best_next_score(next_state, next_shape, weights)
        else:
            total_score = -_place(state, blocks, x, d, weights, False)[0]

        if total_score > best_score:
            best_score = total_score
            best_rot = rot
            best_x = x

    if best_score == _NEG_INF:
        return None

    return (best_rot, best_x, best_score)


# ---------------------------------------------------------------------------
# Hold-aware search (play vs. hold branch comparison)
# ---------------------------------------------------------------------------

def find_best_move_with_hold(grid, shape, next_shape, held_piece, is_held,
                              weights):
    """
    Find the best move considering both branches:
      A) Play the current piece as-is
      B) Hold current piece and play held_piece (or next_shape if no held piece)

    Args:
        grid: 2D integer grid
        shape: Current piece key ('T', 'I', etc.)
        next_shape: Next piece in preview queue
        held_piece: Currently held piece key (str or None)
        is_held: True if hold was already used this turn
        weights: list of 10+ floats

    Returns:
        (best_rot, best_x, should_hold) or None
    """
    # ---- Branch A: Play current piece normally ----
    result_a = find_best_move_scored(grid, shape, next_shape, weights)
    score_a = result_a[2] if result_a is not None else float("-inf")

    # ---- Branch B: Hold + play held piece ----
    # Only consider hold if we haven't already held this turn
    score_b = float("-inf")
    result_b = None
    if not is_held:
        if held_piece is not None:
            # Swap: play held_piece, next lookahead = next_shape
            play_piece = held_piece
            lookahead_piece = next_shape
        else:
            # First hold ever: play next_shape, next lookahead = (unknown, use None)
            play_piece = next_shape
            lookahead_piece = None

        result_b = find_best_move_scored(grid, play_piece, lookahead_piece, weights)
        if result_b is not None:
            score_b = result_b[2]

    # ---- Pick the better branch ----
    if score_a >= score_b:
        if result_a is None:
            return None
        return (result_a[0], result_a[1], False)    # Play current, don't hold
    else:
        if result_b is None:
            return None
        return (result_b[0], result_b[1], True)     # Hold, then play
