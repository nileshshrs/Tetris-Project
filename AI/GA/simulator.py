"""
Headless Tetris simulator for GA training and benchmarking.

Plays a complete game with a given weight vector using the SAME rules and the
SAME decision code as the real game:
  - 7-bag piece generator from a seeded RNG (same as Tetris/main.py)
  - 3-piece preview queue; the AI sees the next piece only (as at runtime)
  - hold-aware decision via evaluator.find_best_move_with_hold
    (identical to the dual-worker play-vs-hold comparison)
  - spawn-collision game over (same check as Game.create_new_tetromino)

Time model: a virtual clock, not wall-clock. In the real game the AI's
`delay` spaces out consecutive hard drops, and holding costs no time, so every
locked piece costs exactly `ai_delay_ms` of game time:
    time = pieces_placed * ai_delay_ms
Default 130 ms (~7.7 pieces/sec), matching the GA agent class
(AI/GA/tetris_ai.py) and close to the fastest recorded 40L sprint (~7.5 PPS,
~133 ms). For reference: the Guinness-recorded sprint pace is 5.135 PPS
(195 ms) and the standalone TetrisAI uses 60 ms.

What it does NOT model: gravity, lock delay, worker-process latency. Pieces are
placed exactly where the AI intended, i.e. the AI is assumed to always be
faster than gravity. Results depend only on the weights, the seed and the
delay, never on how busy the computer is.

No Pygame display or worker processes are used (settings.py still imports the
pygame package for Vector2, but nothing is initialised).
"""

import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
for _p in (_ROOT, os.path.join(_ROOT, "Tetris"), os.path.join(_ROOT, "AI")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from Tetris.settings import (  # noqa: E402
    COLUMNS, SCORE_DATA, TETROMINOS, create_7bag, get_next_tetromino,
)
from Tetris.core import TetrisCore  # noqa: E402
from AI.evaluator import find_best_move_with_hold  # noqa: E402

PREVIEW_SIZE = 3                       # same as Main.next_shapes
SPAWN_X = (COLUMNS // 2) - 1           # same as settings.BLOCK_OFFSET.x
SPAWN_Y = -1                           # same as settings.BLOCK_OFFSET.y


def play_game(weights, seed, max_pieces=500, ai_delay_ms=130):
    """
    Play one game.

    Args:
        weights: list of 10 floats (evaluator weight order)
        seed: int, seeds the 7-bag RNG (same seed -> same piece sequence)
        max_pieces: stop after this many locked pieces (agent "survived")
        ai_delay_ms: game time charged per locked piece (virtual clock)

    Returns:
        dict with lines, pieces, score, time_s, lines_per_sec,
        num_1line..num_tetris, topped_out
    """
    rng = random.Random(seed)
    bag = create_7bag(rng)
    queue = [get_next_tetromino(bag, rng) for _ in range(PREVIEW_SIZE)]
    current = queue.pop(0)
    queue.append(get_next_tetromino(bag, rng))

    grid = TetrisCore.create_grid()
    held = None
    is_held = False

    pieces = 0
    lines = 0
    score = 0
    clears = {1: 0, 2: 0, 3: 0, 4: 0}
    topped_out = False

    def advance():
        """Mirror of Main.get_next_shape: take next piece, refill queue."""
        nonlocal is_held
        nxt = queue.pop(0)
        queue.append(get_next_tetromino(bag, rng))
        is_held = False
        return nxt

    while pieces < max_pieces:
        decision = find_best_move_with_hold(
            grid, current, queue[0], held, is_held, weights
        )
        if decision is None:            # no legal placement -> topped out
            topped_out = True
            break

        rot, x, should_hold = decision

        if should_hold:
            # Mirror of Game.hold_piece
            if held is None:
                held = current
                current = advance()
            else:
                current, held = held, current
            is_held = True
            continue

        blocks = TETROMINOS[current]['rotations'][rot]
        drop_y = TetrisCore.hard_drop_y_fast(grid, blocks, x, SPAWN_Y)
        TetrisCore.lock_piece_mut(grid, blocks, x, drop_y)
        cleared = TetrisCore.clear_lines_mut(grid)
        pieces += 1

        if cleared:
            lines += cleared
            score += SCORE_DATA[cleared]          # level is always 1 in this project
            clears[cleared] += 1

        current = advance()
        if TetrisCore.is_game_over(grid, current, 0, SPAWN_X, SPAWN_Y):
            topped_out = True
            break

    time_s = pieces * ai_delay_ms / 1000.0

    return {
        "lines": lines,
        "pieces": pieces,
        "score": score,
        "time_s": time_s,
        "lines_per_sec": (lines / time_s) if time_s > 0 else 0.0,
        "num_1line": clears[1],
        "num_2line": clears[2],
        "num_3line": clears[3],
        "num_tetris": clears[4],
        "topped_out": topped_out,
    }


def play_job(job):
    """Pool-friendly wrapper: job = (agent_idx, game_idx, weights, seed, max_pieces, ai_delay_ms)."""
    agent_idx, game_idx, weights, seed, max_pieces, ai_delay_ms = job
    return agent_idx, game_idx, play_game(weights, seed, max_pieces, ai_delay_ms)
