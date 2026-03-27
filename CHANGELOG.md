# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

## 2026-03-27: Phase 1 — Per-Game RNG Isolation

### Added
- **Isolated 7-bag shuffling** (`Tetris/settings.py`) — `create_7bag()` and `get_next_tetromino()` now accept an optional RNG instance so each game can draw pieces from its own independent random stream.
- **Per-game RNG state** (`Tetris/main.py`) — `Main` now creates a dedicated `random.Random` per instance and threads it through all bag draws, preventing cross-game contamination during GA tray execution.

### Fixed
- **Cross-agent RNG contamination** (`Tetris/main.py`, `Tetris/settings.py`) — Parallel games no longer mutate a shared global random state, so agent fitness is no longer biased by the order in which boards consume pieces.

## 2026-03-21: BGM Audio Support

### Added
- **Soundtrack Integration** (`Tetris/main.py`) — Implemented Pygame audio mixer to seamlessly load and indefinitely loop "Tetris Effect: Connected - Yours Forever" (`yours_forever.mp3`) from the `Tetris/assets/graphics/audio/` directory. Audio stops cleanly upon reaching Game Over.
- **Headless Audio Muting** (`Tetris/main.py`) — Added automatic environment variable check (`os.environ.get("SDL_VIDEODRIVER") != "dummy"`) to ensure music exclusively plays during visual gameplay, keeping headless genetic algorithm training completely silent and CPU-efficient.

## 2026-03-21: Phase 6 — Async Multiprocessing

### Added
- **AI Worker Process** (`AI/worker.py`) — Created a standalone headless worker script that runs the AI computation purely through integer math without Pygame overhead.
- **Async Execution Mode** (`AI/TetrisAI.py`, `AI/GA/tetris_ai.py`) — Implemented `_update_async` logic using `multiprocessing.Pipe` payloads to send game state tuples and receive compute placements without blocking the main event thread.
- **Multiprocessing Infrastructure** (`Tetris/main.py`) — Bootstraps `multiprocessing.Process`, configures connection pipes, and properly safeguards Windows runtime with `freeze_support()`.
- **Parallel Genetic Algorithm Support** (`AI/GA/optimize.py`, `AI/GA/gauntlet.py`) — The GA trainers now completely initialize asynchronously (`use_async_ai=True`), allowing every tray's agent execution instance to isolate evaluation logic into concurrent background OS processes.

### Fixed
- **OS-Agnostic Checkpoint Paths** (`AI/GA/optimize.py`, `AI/GA/gauntlet.py`, `AI/GA/genetic_algorithm.py`) — Replaced hardcoded 'D:\' directory paths with relative path logic (`os.path.join`) so logging functions correctly on any system.
- **Dynamic AI Injection** (`Tetris/game.py`) — Replaced hardcoded standalone TetrisAI dependencies with a configurable `ai_class` and `ai_kwargs` passthrough, enabling the transparent injection of both the Async Player logic and GA Mutated logic.
- **Async Execution Throttle** (`AI/TetrisAI.py`, `AI/GA/tetris_ai.py`) — Fixed a visual overlap parsing bug where the fast gravity (15ms) caused pieces to fall into the stack before the AI could horizontally shift them. The `self.delay` cooldown is now exclusively applied to the hard drop action, allowing instant shifts before the visual pausing queue.

---

## 2026-03-07: Phase 5 — Modern Mechanics (SRS & Timing)

### Added
- **Lock Delay (The "Infinity" Rule)** (`game.py`) — The piece's lock timer now resets when it is successfully rotated or moved horizontally, allowing for continuous manipulation against the floor before locking.
- **Move Limit Guard** (`game.py`) — Implemented a maximum of 15 timer resets (`lock_move_count`) to prevent infinite stalling on the ground.
- **DAS & ARR Horizontal Tracking** (`game.py`) — Overhauled horizontal movement handling. It now detects initial directional presses (applying `DAS_DELAY`) distinct from held keys (applying rapid `ARR_SPEED`), resulting in incredibly snappy, professional-feeling Guideline piece movement.

### Changed
- `timerss['horizontal move']` initialization now properly maps to `DAS_DELAY` instead of the old singular `MOVE_WAIT_TIME`.
- Setting parameters (`DAS_DELAY = 150`, `ARR_SPEED = 30`) formally replace `MOVE_WAIT_TIME` in `settings.py`.

---

## 2026-03-07: Phase 4 — High-Performance Renderer

### Changed
- **Total elimination of Sprite Groups** (`game.py`) — Removed all `pygame.sprite.Group` overhead and deleted the `Block` class entirely.
- **Background Surface Baking** (`game.py`) — Landed pieces are now baked directly onto a persistent `bg_surface` initialized with the grid backdrop. This means Pygame only blits one static surface per frame instead of redrawing 200 individual block sprites.
- **Procedural Frame Rendering** (`game.py`) — `Game.run()` now pure functional rendering:
  1. Blit `bg_surface` to screen
  2. Draw ghost piece outline dynamically
  3. Draw active piece blocks dynamically using pure variables instead of Sprite rects
- **Pure Integer `game_data`** (`game.py`) — The grid matrix now simply stores colors (`#ff0000`, etc.) instead of truthy object references, removing any lingering memory footprint and cleanly decoupling logic from rendering.
- **Decoupled `Tetrominos` class** (`game.py`) — Rebuilt as a pure logic wrapper. It entirely defers collision (`is_valid_pos`), dropping (`hard_drop_y`), and kicking (`try_rotate`) logic to the static `core.py` engine, making its codebase ~75% smaller and strictly integer-based.
- **Micro-Optimization: Grid Line Caching** (`game.py`) — Moved the 30 `pygame.draw.line` calls out of the main `draw_grid()` loop. The grid outline is now baked once during `__init__` into `self.line_surface`, which is blitted directly.
- **Micro-Optimization: Zero-Object Rendering** (`game.py`) — Eliminated all remaining `pygame.Rect` object instantiations from the drawing functions (`check_finished_rows`, `lock_tetromino`, `run`). Everything now passes raw Python tuples `(x, y, w, h)` directly to Pygame's C-bindings, achieving absolute zero-object allocation per frame.

### Removed
- `Block` class in `game.py` completely deleted.
- `self.sprites` in `Game.run()` and `__init__` completely deleted.
- Any manual bounds-checking left in `Tetrominos` deleted, handled by `core.py`.

### Performance Impact
| Metric | Before | After |
|--------|--------|-------|
| Pygame Sprite Groups | 1 | 0 |
| Number of items drawn individually per frame | 200+ (active blocks + all landed blocks) | 8 (4 active piece rects + 4 ghost rects) |
| Grid storage memory | 2D list of Heavy `Block` Class Objects | 2D list of Strings/Tuples |

---

## 2026-03-01: Phase 1–3 Second Polish Pass

### Fixed

- **`timers.py` `set_interval()` silent no-op** — Previously ignored calls when timer was inactive, meaning the duration wouldn't update. Now always updates `self.duration` and only resets `start_time` when active.
- **`game.py` AI import path** — Changed from fragile `sys.path.append(os.path.abspath('.'))` (CWD-dependent) to `__file__`-relative path. Now works regardless of which directory the script is run from.
- **`game.py` `move_down()` return value** — `Tetrominos.move_down()` now returns `True`/`False` so the AI's fallback hard-drop loop (`while tetromino.move_down()`) works correctly.
- **`game.py` `next_move_vertical_collide()` verbose return** — Simplified `return True if any(...) else False` to `return any(...)`.
- **`readme.md` GA run commands** — Fixed `python GA/optimize.py` → `python AI/GA/optimize.py` and `python GA/gauntlet.py` → `python AI/GA/gauntlet.py`.

### Removed

- **`score.py` border** — Completely removed the static border surrounding the score/timer surface for a cleaner UI.
- **`self.current_bag`** (`game.py`) — `Game` created its own bag but never used it; piece spawning is handled entirely by `Main.get_next_shape()`. Initial tetromino now spawns through the same pipeline.
- **`self.tetromino_touching_floor`** (`game.py`) — Set to `False` but never read by any code.
- **`current_bag` module-level variable** (`settings.py`) — Created at import time but unused; both `Game` and `Main` create their own bags.
- **Stale "tray mode" comments** (`game.py`) — Four comments referencing "the next two lines" where those lines had been removed.
- **Unused `_lock`/`_unlock` aliases** (`AI/TetrisAI.py`) — Dead local variables and misleading docstring in `_evaluate_next()`.
- **Unused `load` import** (`lines.py`) — `from pygame.image import load` was never used.
- **Scaffolding comment** (`score.py`) — Leftover `# <--- ADD THIS LINE` instruction.

### Changed

- **`timers.py` indentation** — Converted tabs to 4-space indentation, matching all other files in the project.

### Files Modified

| File | Changes |
|------|---------|
| `Tetris/game.py` | Robust AI import, removed dead `current_bag`/`tetromino_touching_floor`/stale comments, `move_down()` returns bool, simplified `next_move_vertical_collide` |
| `Tetris/timers.py` | Tabs→spaces, `set_interval()` always updates duration |
| `Tetris/score.py` | Removed border rendering, removed scaffolding comment |
| `Tetris/lines.py` | Removed unused `load` import |
| `Tetris/settings.py` | Removed dead module-level `current_bag` |
| `AI/TetrisAI.py` | Removed unused `_lock`/`_unlock` aliases, fixed docstring |
| `readme.md` | Fixed GA run command paths |

---

## 2026-03-01: Phase 1–3 Final Polish

### Fixed

- **`w1` weight set → list** (`AI/TetrisAI.py`) — `w1` used curly braces (`set`) instead of square brackets (`list`). Sets are unordered, so indexing by position would silently scramble weights. Changed to `list`.
- **`fills_well` boundary guard** (`AI/TetrisAI.py`, `AI/GA/tetris_ai.py`) — Added defensive `vy >= ROWS - 1` check before accessing `board[vy + 1]` to prevent potential `IndexError`.

### Removed

- **`TETROMINOS_WEIGHTS`** (`settings.py`) — Dead code leftover from the deleted weighted bag system. The active 7-bag doesn't use it.
- **`self.rows` / `self.cols`** (`AI/GA/tetris_ai.py`) — Instance attributes set but never read; module-level `ROWS`/`COLUMNS` constants are used directly.
- **`core_grid` + `_sync_core_grid()`** (`game.py`) — Integer mirror grid maintained on every line clear but never read after shadow validation removal. Eliminated unnecessary `grid_from_game_data()` call per line clear.
- **`create_new_tetromino_called`** (`game.py`) — Flag set in 4 places (`__init__`, `move_horizontal`, `move_down`, `rotate`) but never read by any code.
- **`else: pass`** (`game.py: Tetrominos.move_down()`) — Unnecessary empty branch removed.
- **`self.Tetrominos`** (`AI/TetrisAI.py`, `AI/GA/tetris_ai.py`) — `tetromino_class` parameter and attribute removed from both AI constructors. The Phase 3 AI never instantiates Tetromino objects.
- **Redundant reachability loop** (`core.py: evaluate_all_placements()`) — `hard_drop_y_fast()` already validates every Y during its downward scan; the explicit reachability re-check was proving the same thing twice.

### Files Modified

| File | Changes |
|------|---------|
| `AI/TetrisAI.py` | `w1` set→list, `fills_well` guard, removed `self.Tetrominos` |
| `AI/GA/tetris_ai.py` | `fills_well` guard, removed `self.rows`/`self.cols`/`self.Tetrominos` |
| `Tetris/game.py` | Removed `core_grid`, `_sync_core_grid()`, `create_new_tetromino_called`, `else: pass`; updated AI constructor call |
| `Tetris/settings.py` | Removed dead `TETROMINOS_WEIGHTS` |
| `Tetris/core.py` | Removed redundant reachability loop, simplified visibility check |

---

## 2026-02-28: Phase 2 & 3 Polish

### Changed (Phase 2 — game.py)

- **Removed shadow validation** — All 6 per-frame collision shadow checks (vertical, horizontal left/right) and game-over mismatch detection removed. Verified zero mismatches across extensive play; now pure overhead eliminated.
- **Simplified `core_grid` sync** — Replaced 4 scattered manual sync points (`hold_piece`, `perform_hard_drop`, `lock_tetromino`, `check_finished_rows`) with single `_sync_core_grid()` helper that rebuilds from `game_data` as single source of truth.

### Changed (Phase 3 — TetrisAI.py & GA/tetris_ai.py)

- **Single-pass board features** — Merged 4 separate helper functions (`_column_heights`, `_count_holes_and_blockades`, `_almost_full_lines`, `_find_deepest_well`) into one `_compute_board_features()` that extracts all 7 heuristic features in a single traversal of the 200-cell board.
- **Zero-copy line clearing** — Added `_count_cleared_lines()` that counts cleared lines by checking only the rows touched by the piece, without copying or mutating the grid. Eliminates `lock_piece` + `clear_lines` grid copies for the current piece's cost evaluation.
- **Lookahead grid copies deferred** — `lock_piece` + `clear_lines` grid copies only happen when lookahead is actually needed (not for every placement).

### Performance Impact

| Optimization | Board scans saved per placement | Grid copies saved |
|---|---|---|
| Single-pass `_compute_board_features` | 3 (was 4 passes, now 1) | — |
| `_count_cleared_lines` (current piece) | — | 2 per placement (~68 total) |
| Lookahead deferred | — | Conditional instead of always |
| Shadow validation removed | 6 collision checks per frame | — |

### Files Modified

| File | Changes |
|------|---------|
| `Tetris/game.py` | Removed shadow validation, added `_sync_core_grid()`, simplified sync points |
| `AI/TetrisAI.py` | Single-pass features, zero-copy line count, deferred lookahead copies |
| `AI/GA/tetris_ai.py` | Same optimizations as TetrisAI.py |

---

## 2026-02-28: Phase 3 — Quantum AI Refactor

### Added

- **`TetrisCore.is_valid_pos_fast()`** — Collision check accepting pre-fetched block list (skips TETROMINOS dict lookup every call)
- **`TetrisCore.hard_drop_y_fast()`** — Landing Y calculation using pre-fetched blocks
- **`TetrisCore.lock_piece_mut()`** — In-place grid mutation for AI simulation (returns written cells for undo)
- **`TetrisCore.unlock_piece_mut()`** — Undo a `lock_piece_mut()` call
- **`TetrisCore.clear_lines_mut()`** — In-place line clear (mutates grid, returns count)
- **`TetrisCore.evaluate_all_placements()`** — Batch-generates all valid `(rot, x, drop_y, blocks)` for a shape with vertical reachability checking
- **Vertical reachability check** — AI verifies the piece can drop straight down from spawn to landing without obstruction. Prevents "hallucinating" placements in unreachable pockets.

### Changed

- **`AI/TetrisAI.py`** — Complete rewrite using pure integer math
  - `_find_best_move()`: Uses `evaluate_all_placements()` for batch position generation
  - `_evaluate_next()`: Lookahead uses `TetrisCore.lock_piece()` + `clear_lines()` (line clearing between pieces!)
  - `_cost_function()`: No-copy heuristic using `virtual_coords` frozenset as obstacles
  - `fills_well` check adapted to use `(vx, vy)` tuples instead of sprite block objects
  - `update()`: Translates absolute `(rot, x)` to relative `(rotations_needed, dx_needed)` using `tetromino.rotation_index` and `tetromino.pivot.x`
  - All heuristic weights preserved **exactly** (`1.275, 4.0, 1.2, 0.8, 0.5, 3.0, clear: 20/5/2/0.1`)
- **`AI/GA/tetris_ai.py`** — Same refactor with GA-tunable weights array
- **All 4 rotation states** now evaluated for every piece (except O = 1). Fixed pre-existing bug where I, S, Z only checked 2 rotations.

### Removed

- **`_clone_tetromino()`** — Deleted entirely. Zero class instantiation in the AI search loop.
- **`pygame.sprite.Group()`** usage in AI evaluation — No more dummy sprite groups
- **`_is_unplayable()`** — Replaced by `evaluate_all_placements()` bounds checking

### Performance

| Metric | Before | After |
|--------|--------|-------|
| Object instantiation per eval | ~80 Tetrominos + ~320 Blocks per piece | **0** |
| Grid copies per placement | 2 (clone + sim_board) | 1 (lock_piece for lookahead) |
| Dict lookups per collision check | 1 (`TETROMINOS[shape]['rotations'][rot]`) | 0 (pre-fetched) |
| Rotation states evaluated (I/S/Z) | 2 | **4** (more placements, better decisions) |

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| `frozenset(virtual_coords)` for heuristic | O(1) membership test without grid copy. Safer than mutate-then-restore. |
| Absolute `(rot, x)` → relative translation | Cleaner separation between search (pure math) and execution (Pygame) |
| Vertical reachability only (no BFS) | Conservative — rejects some valid positions but never suggests impossible ones |
| Preserved `_blockades` scan direction | Weights were tuned around its top-to-bottom quirk |

### Files Modified

| File | Changes |
|------|---------|
| `Tetris/core.py` | 6 new methods: `is_valid_pos_fast`, `hard_drop_y_fast`, `lock_piece_mut`, `unlock_piece_mut`, `clear_lines_mut`, `evaluate_all_placements` |
| `AI/TetrisAI.py` | 🔄 Complete rewrite — zero object instantiation, pure integer math |
| `AI/GA/tetris_ai.py` | 🔄 Complete rewrite — same architecture with GA weights |

### Verification

- ✅ 30/30 Phase 3 smoke tests passed (fast methods match originals, placements valid, cost function correct)
- ✅ All 4 rotations evaluated for every non-O piece
- ✅ `lock_piece_mut` / `unlock_piece_mut` roundtrip preserves grid
- ✅ `clear_lines_mut` result matches immutable `clear_lines`
- ✅ `_find_best_move` produces valid placements on empty grid
- ✅ Zero Pygame imports in AI search loop core logic

## 2026-02-14: Phase 2 — Atomic Logic Core

### Added

- **`Tetris/core.py`** — New headless logic engine with zero Pygame dependency
  - `TetrisCore.is_valid_pos()`: High-speed collision detection using pure integer math
  - `TetrisCore.clear_lines()`: Immutable line clear — returns new grid + count
  - `TetrisCore.hard_drop_y()`: Calculate landing Y without mutation (ghost piece / AI)
  - `TetrisCore.try_rotate()`: SRS rotation with wall kicks as pure logic
  - `TetrisCore.lock_piece()`: Immutable piece locking — returns new grid
  - `TetrisCore.get_piece_cells()`: Get absolute grid positions of all 4 blocks
  - `TetrisCore.is_game_over()`: Spawn collision check
  - `TetrisCore.grid_from_game_data()`: Convert sprite grid to integer grid
  - `TetrisCore.create_grid()`: Factory for empty integer grids
  - All methods are `@staticmethod` — no instance state, safe for parallel use

- **Shadow validation** in `Game.run()` (`game.py`)
  - Every frame, collision is checked by BOTH the old sprite system AND the new core engine
  - Validates: vertical collision (down), horizontal collision (left + right), game-over spawn
  - Mismatches print `⚠️ MISMATCH` with full state for debugging
  - Verified: **zero mismatches** during AI gameplay testing

### Fixed

- **`Block.horizontal_collide()` negative-Y bug** (pre-existing, caught by shadow validation)
  - When piece was above the playfield (`pos.y = -1`), Python's negative indexing caused
    `game_data[-1]` to read the BOTTOM row, producing false collision positives
  - Added negative-Y guard matching `vertical_collide()`'s existing pattern
  - **This bug was invisible before** — shadow validation between core and sprite systems exposed it

- **`check_finished_rows()` simplified** — replaced buggy row-shifting loop
  - Old code: O(rows × cols) nested shifting that produced wrong results for non-contiguous clears
  - New code: Per-sprite adjustment — each block drops by count of cleared rows below it
  - Then rebuilds `game_data` + `core_grid` from sprites

### Changed

- **`Game.__init__()`** — added `self.core_grid` integer mirror of `game_data`
- **`Game.lock_tetromino()`** — syncs `core_grid` when pieces lock
- **`Game.perform_hard_drop()`** — syncs `core_grid` on hard drop
- **`Game.hold_piece()`** — clears `core_grid` cells when holding
- **`Game.check_finished_rows()`** — rebuilds `core_grid` from sprites after line clear
- **`Game.create_new_tetromino()`** — shadow-validates game-over against `TetrisCore.is_game_over()`
- **`Tetrominos.get_ghost_positions()`** — now delegates to `TetrisCore.hard_drop_y()` + `get_piece_cells()`
  instead of manual Vector2 loop, improving consistency and speed

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| All methods are `@staticmethod` | No instance state needed — grid passed in. Ready for Phase 3 AI and Phase 6 multiprocessing |
| Zero Pygame imports in `core.py` | Can be imported by AI workers without display init |
| Negative Y allowed in bounds check | Matches spawn behavior where pieces start above playfield |
| Immutable operations (`lock_piece`, `clear_lines`) | Returns new grid — original never mutated. Safe for AI simulation |

### Files Modified

| File | Changes |
|------|---------|
| `Tetris/core.py` | 🆕 Created — headless logic engine |
| `Tetris/game.py` | Shadow validation (V + H + game-over), `core_grid` sync, ghost delegation, `horizontal_collide` bug fix, `check_finished_rows` simplification |

### Verification

- ✅ 15 unit tests passed (collision, line clear, hard drop, rotation, wall kicks, immutability)
- ✅ Zero collision mismatches during live AI gameplay (vertical + horizontal + game-over)
- ✅ `core.py` has zero Pygame imports
- ✅ Shadow validation caught and fixed a real bug in `Block.horizontal_collide()`

---

## 2026-02-14: Phase 1 Polish — AI Rotation Coverage, CCW Rotation, Code Cleanup

### Fixed

- **AI now evaluates all 4 rotation states for I, S, Z pieces** (`AI/TetrisAI.py`, `AI/GA/tetris_ai.py`)
  - Previously hardcoded `max_rotations = 2` for I, S, and Z pieces
  - With SRS, all pieces have 4 distinct rotation states — the AI was missing potential optimal placements
  - Simplified logic: O-piece = 1 rotation, all others = 4 rotations

### Changed

- **`rotate()` uses plain tuples instead of `pygame.Vector2`** (`game.py`)
  - Test positions in `Tetrominos.rotate()` now use `(x, y)` tuples instead of `pygame.Vector2(x, y)`
  - `_is_valid_position()` updated to use index-based access `pos[0]`, `pos[1]`
  - Consistent with Phase 1's "pure integer tuples" design philosophy
  - Eliminates unnecessary object creation during rotation validation

### Added

- **Counterclockwise rotation keybinding** (`game.py`)
  - `UP` arrow → clockwise rotation (unchanged)
  - `Z` key → counterclockwise rotation (new)
  - Matches standard Tetris Guideline controls

### Removed

- **Dead commented-out code in `settings.py`**
  - Removed ~46 lines of old weighted bag system (`create_weighted_bag`, `get_next_tetromino` with streak prevention)
  - The active 7-bag system (`create_7bag`, `get_next_tetromino`) was already in place
  - `settings.py` reduced from 230 → 184 lines

### Files Modified

| File | Changes |
|------|---------|
| `AI/TetrisAI.py` | `max_rotations` fix for I/S/Z (2 locations) |
| `AI/GA/tetris_ai.py` | `max_rotations` fix for I/S/Z (2 locations) |
| `Tetris/game.py` | Tuple-based rotation test, CCW keybinding |
| `Tetris/settings.py` | Removed dead code |

---

## 2026-02-07: Phase 1 Complete — I-Piece SRS Fix

### Fixed

- **I-Piece Rotation States** (`settings.py`)
  - Corrected I-piece to have **4 distinct rotation states** as per official SRS specification
  - Previously states 0/2 and 1/3 were identical (incorrect)
  - Now each state occupies different grid positions, enabling proper wall kick behavior

  | State | Before (Incorrect) | After (SRS-Compliant) |
  |-------|-------------------|----------------------|
  | 0 | `[(0,0), (-1,0), (1,0), (2,0)]` | `[(-1,0), (0,0), (1,0), (2,0)]` |
  | 1 | `[(0,0), (0,-1), (0,1), (0,2)]` | `[(0,-1), (0,0), (0,1), (0,2)]` |
  | 2 | *Same as State 0* ❌ | `[(-1,1), (0,1), (1,1), (2,1)]` |
  | 3 | *Same as State 1* ❌ | `[(1,-1), (1,0), (1,1), (1,2)]` |

### Why This Matters

- **Correct wall kicks**: The SRS kick tables have different offsets for 0→1 vs 2→3 transitions
- **Proper I-piece behavior**: Matches official Tetris Guideline games
- **Phase 1 now complete**: All static geometry foundation requirements satisfied

---

## 2026-02-07: Phase 1 — SRS Implementation

### Added

- **Static Rotation Tables** (`settings.py`)
  - Replaced the single `'shape'` key with `'rotations'` containing all 4 rotation states per tetromino
  - All coordinates use pure integer tuples (no `pygame.Vector2`)
  - Consistent pivot point `(0,0)` across all rotation states

- **SRS Wall Kick Tables** (`settings.py`)
  - `SRS_KICKS_GENERAL`: Official kick offsets for J, L, S, Z, T pieces
  - `SRS_KICKS_I`: Special kick offsets for the I-piece
  - Each rotation transition has 5 kick tests

- **Pivot Tracking** (`game.py`)
  - `Tetrominos.rotation_index`: Tracks current rotation state (0-3)
  - `Tetrominos.pivot`: Explicit pivot position for accurate positioning

### Changed

- **Tetrominos Class** (`game.py`)
  - `rotate()` method now uses static table lookup instead of runtime math
  - Block positions calculated from pivot + static offsets
  - `move_horizontal()` and `move_down()` now keep pivot in sync

- **Block Class** (`game.py`)
  - Added `use_offset` parameter for backward compatibility
  - Removed `rotate()` method (no longer needed)

### Removed

- Runtime trigonometry calculations (`pygame.Vector2.rotate(90)`)
- Ad-hoc wall kick offsets (replaced with official SRS tables)

---

## Why This Matters

### 🚀 Performance Advantages

| Benefit | Description |
|---------|-------------|
| **Zero runtime calculations** | Rotation is now a simple array index lookup instead of trigonometric operations |
| **Faster AI evaluation** | The AI can evaluate thousands of positions per frame since rotation is O(1) |
| **Reduced CPU overhead** | No more `pygame.Vector2.rotate(90)` calls creating new vector objects |
| **Memory efficiency** | Static tables are defined once at load time, not computed per rotation |

### 🎮 Gameplay Advantages

| Benefit | Description |
|---------|-------------|
| **Official SRS compliance** | Matches the rotation behavior of modern Tetris games (Tetris Guideline) |
| **T-Spin support** | The SRS kick tables enable proper T-Spin detection and execution |
| **Wall kick consistency** | 5 predictable kick tests per rotation instead of ad-hoc offsets |
| **No jitter/teleportation** | Consistent pivot point means pieces rotate exactly as expected |
| **Professional feel** | Rotations behave identically to Tetris Effect, Puyo Puyo Tetris, etc. |

### 🤖 AI Training Advantages

| Benefit | Description |
|---------|-------------|
| **Deterministic rotations** | Same input always produces same output (important for training) |
| **Faster move generation** | AI can enumerate all 4 rotation states without computing them |
| **Better position evaluation** | Reliable kick behavior means AI predictions match actual gameplay |
| **Multiprocessing ready** | Pure integer data is easily serializable for parallel processing |

### 🛠️ Maintainability Advantages

| Benefit | Description |
|---------|-------------|
| **Single source of truth** | All rotation data lives in `settings.py` |
| **Easy to verify** | You can visually inspect the coordinate tables |
| **Easy to modify** | Changing a rotation state is just editing a tuple |
| **Testable** | Static data can be unit tested without Pygame dependencies |

---

## Technical Details

### Before (Runtime Rotation)

```python
# Old approach - calculate rotation at runtime
def rotate(self, pivot):
    distance = self.pos - pivot
    rotated = distance.rotate(90)  # Trigonometry!
    new_position = pivot + rotated
    return new_position
```

### After (Static Lookup)

```python
# New approach - simple index increment
rotation_index = (rotation_index + 1) % 4
blocks = TETROMINOS[shape]['rotations'][rotation_index]  # O(1) lookup
```

### SRS Kick Table Example

```python
SRS_KICKS_GENERAL = {
    (0, 1): [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
    (1, 2): [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)],
    # ... all 8 rotation transitions
}
```

---

## Files Modified

- `Tetris/settings.py`: Added static rotation tables and SRS kick dictionaries
- `Tetris/game.py`: Rewrote `Tetrominos` and `Block` classes for static rotation

## Verification

The implementation was tested to ensure:
- ✅ No piece "jitter" when rotating (consistent pivot)
- ✅ Wall kicks work correctly against walls and placed blocks
- ✅ All 7 tetromino types rotate correctly through all 4 states
- ✅ 360° rotation returns pieces to original position
