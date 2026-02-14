# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

---

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
