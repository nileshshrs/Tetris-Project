"""
Tetris Core — Headless Logic Engine (Phase 2)

Zero Pygame dependency. Pure integer operations on a 2D grid.
This module can be imported by AI workers, multiprocessing pools,
or any context where Pygame is not initialized.

All methods are static — no instance state needed. The grid is
always passed in, making these functions safe for parallel use.
"""

# Import only the data we need from settings (no Pygame objects used here)
from settings import TETROMINOS, SRS_KICKS_GENERAL, SRS_KICKS_I, COLUMNS, ROWS


class TetrisCore:
    """
    High-speed, headless Tetris logic engine.
    
    All methods are static — they operate on the grid passed to them
    and never mutate it (except clear_lines which returns a new grid).
    """

    @staticmethod
    def create_grid(cols=COLUMNS, rows=ROWS):
        """Create a fresh empty grid (2D list of integers)."""
        return [[0 for _ in range(cols)] for _ in range(rows)]

    @staticmethod
    def is_valid_pos(grid, shape_key, rot_idx, pos_x, pos_y):
        """
        High-speed collision check using pure integer math.
        
        Args:
            grid: 2D list of ints (0 = empty, non-zero = occupied)
            shape_key: Tetromino name ('T', 'I', 'O', etc.)
            rot_idx: Rotation state index (0-3)
            pos_x: Pivot X position (column)
            pos_y: Pivot Y position (row)
        
        Returns:
            True if the piece at this position/rotation is valid (no collision).
        """
        rows = len(grid)
        cols = len(grid[0]) if rows > 0 else 0
        blocks = TETROMINOS[shape_key]['rotations'][rot_idx]

        for bx, by in blocks:
            cx = int(pos_x + bx)
            cy = int(pos_y + by)

            # Boundary check — allow negative Y (spawn area above playfield)
            if cx < 0 or cx >= cols or cy >= rows:
                return False

            # Collision check — only for cells within the visible grid
            if cy >= 0 and grid[cy][cx] != 0:
                return False

        return True

    @staticmethod
    def clear_lines(grid):
        """
        Remove all fully filled rows and return the new grid + count.
        
        Does NOT mutate the input grid — returns a brand new grid.
        
        Args:
            grid: 2D list of ints
            
        Returns:
            (new_grid, lines_cleared): Tuple of new grid and number of lines cleared.
        """
        rows = len(grid)
        cols = len(grid[0]) if rows > 0 else 0

        # Keep rows that still have at least one empty cell
        cleaned = [row[:] for row in grid if 0 in row]
        lines_cleared = rows - len(cleaned)

        if lines_cleared == 0:
            return grid, 0

        # Reconstruct: pad empty rows at top + surviving rows at bottom
        new_grid = [[0] * cols for _ in range(lines_cleared)] + cleaned
        return new_grid, lines_cleared

    @staticmethod
    def hard_drop_y(grid, shape_key, rot_idx, pos_x, pos_y):
        """
        Calculate the Y position where a piece would land (hard drop).
        
        Scans downward from the given position until collision.
        Does NOT mutate anything.
        
        Args:
            grid: 2D list of ints
            shape_key: Tetromino name
            rot_idx: Rotation state (0-3)
            pos_x: Pivot X
            pos_y: Pivot Y (starting position)
            
        Returns:
            The lowest valid Y for the pivot (landing position).
        """
        y = pos_y
        while TetrisCore.is_valid_pos(grid, shape_key, rot_idx, pos_x, y + 1):
            y += 1
        return y

    @staticmethod
    def try_rotate(grid, shape_key, old_rot, pos_x, pos_y, clockwise=True):
        """
        Attempt SRS rotation with wall kicks. Pure logic, no side effects.
        
        Args:
            grid: 2D list of ints
            shape_key: Tetromino name
            old_rot: Current rotation index (0-3)
            pos_x: Current pivot X
            pos_y: Current pivot Y
            clockwise: True for CW, False for CCW
            
        Returns:
            (success, new_rot, new_x, new_y) — the resulting state if successful,
            or (False, old_rot, pos_x, pos_y) if all kicks fail.
        """
        if shape_key == 'O':
            return (True, old_rot, pos_x, pos_y)  # O doesn't rotate

        new_rot = (old_rot + 1) % 4 if clockwise else (old_rot - 1) % 4

        # Select the appropriate kick table
        kicks = SRS_KICKS_I if shape_key == 'I' else SRS_KICKS_GENERAL
        kick_offsets = kicks.get((old_rot, new_rot), [(0, 0)])

        for dx, dy in kick_offsets:
            test_x = pos_x + dx
            test_y = pos_y + dy

            if TetrisCore.is_valid_pos(grid, shape_key, new_rot, test_x, test_y):
                return (True, new_rot, test_x, test_y)

        # All kicks failed
        return (False, old_rot, pos_x, pos_y)

    @staticmethod
    def lock_piece(grid, shape_key, rot_idx, pos_x, pos_y):
        """
        Lock a piece onto the grid. Returns a NEW grid (does not mutate input).
        
        Each occupied cell is marked with 1 (or could be a color index).
        
        Args:
            grid: 2D list of ints
            shape_key: Tetromino name
            rot_idx: Rotation state (0-3)
            pos_x: Pivot X
            pos_y: Pivot Y
            
        Returns:
            new_grid: Grid with the piece locked in place.
        """
        new_grid = [row[:] for row in grid]
        blocks = TETROMINOS[shape_key]['rotations'][rot_idx]

        for bx, by in blocks:
            cx = int(pos_x + bx)
            cy = int(pos_y + by)
            if 0 <= cx < len(new_grid[0]) and 0 <= cy < len(new_grid):
                new_grid[cy][cx] = 1

        return new_grid

    @staticmethod
    def get_piece_cells(shape_key, rot_idx, pos_x, pos_y):
        """
        Get the absolute grid positions of all 4 blocks of a piece.
        
        Args:
            shape_key: Tetromino name
            rot_idx: Rotation state (0-3)
            pos_x: Pivot X
            pos_y: Pivot Y
            
        Returns:
            List of 4 (x, y) tuples — absolute grid coordinates.
        """
        blocks = TETROMINOS[shape_key]['rotations'][rot_idx]
        return [(int(pos_x + bx), int(pos_y + by)) for bx, by in blocks]

    @staticmethod
    def is_game_over(grid, shape_key, rot_idx, pos_x, pos_y):
        """
        Check if placing a new piece at spawn would cause game over.
        
        Returns True if ANY block of the piece overlaps an occupied cell
        within the visible grid (y >= 0).
        """
        blocks = TETROMINOS[shape_key]['rotations'][rot_idx]
        for bx, by in blocks:
            cx = int(pos_x + bx)
            cy = int(pos_y + by)
            if 0 <= cx < len(grid[0]) and 0 <= cy < len(grid):
                if grid[cy][cx] != 0:
                    return True
        return False

    @staticmethod
    def grid_from_game_data(game_data, rows=ROWS, cols=COLUMNS):
        """
        Convert the sprite-based game_data grid to a pure integer grid.
        
        Used for shadow validation — creates an integer snapshot of
        the current game_data (which stores Block objects or 0).
        
        Args:
            game_data: 2D list where cells are either 0 or Block objects
            
        Returns:
            2D list of ints (0 = empty, 1 = occupied)
        """
        return [
            [1 if game_data[r][c] else 0 for c in range(cols)]
            for r in range(rows)
        ]
