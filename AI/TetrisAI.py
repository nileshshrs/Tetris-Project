import pygame
from settings import ROWS, COLUMNS

def count_almost_full_lines(board, allowed_gaps=2):
    count = 0
    for row in board:
        empty = sum(1 for cell in row if cell == 0)
        if 1 <= empty <= allowed_gaps:
            count += 1
    return count

def find_deepest_well(board):
    rows, cols = len(board), len(board[0])
    col_heights = [rows - next((r for r in range(rows) if board[r][c]), rows) for c in range(cols)]
    max_well_depth = 0
    well_col = -1
    for c in range(cols):
        left = col_heights[c-1] if c > 0 else rows
        right = col_heights[c+1] if c < cols-1 else rows
        well_depth = min(left, right) - col_heights[c]
        if well_depth > max_well_depth:
            max_well_depth = well_depth
            well_col = c
    return well_col, max_well_depth

class TetrisAI:
    def __init__(self, game, tetromino_class):
        self.game = game
        self.Tetrominos = tetromino_class
        self.last_action_time = 0
        self.delay = 200
        self.rows = ROWS
        self.cols = COLUMNS

    def _is_unplayable(self, candidate):
        for b in candidate.blocks:
            if int(b.pos.y) < 0:
                return True
        return False

    def update(self, next_shape):
        if self.game.is_game_over or not self.game.tetromino or not next_shape:
            return

        now = pygame.time.get_ticks()
        if now - self.last_action_time < self.delay:
            return

        base_board = [
            [1 if self.game.game_data[r][c] else 0 for c in range(self.cols)]
            for r in range(self.rows)
        ]
        original = self.game.tetromino

        best_score = float("-inf")
        best_rotation = 0
        best_dx = 0

        shape = getattr(original, "shape", None)
        if shape == "O":
            max_rotations = 1
        elif shape in ("I", "S", "Z"):
            max_rotations = 2
        else:
            max_rotations = 4

        for rotation_count in range(max_rotations):
            test_piece = self._clone_tetromino(original)
            for _ in range(rotation_count):
                test_piece.rotate()

            leftmost = min(int(b.pos.x) for b in test_piece.blocks)
            rightmost = max(int(b.pos.x) for b in test_piece.blocks)
            dx_min = -leftmost
            dx_max = (self.cols - 1) - rightmost

            for dx in range(dx_min, dx_max + 1):
                candidate = self._clone_tetromino(test_piece)
                for b in candidate.blocks:
                    b.pos.x += dx

                while True:
                    collision = False
                    for b in candidate.blocks:
                        x = int(b.pos.x)
                        y = int(b.pos.y)
                        if y + 1 >= self.rows or (y + 1 >= 0 and base_board[y + 1][x]):
                            collision = True
                            break
                    if not collision:
                        for b in candidate.blocks:
                            b.pos.y += 1
                    else:
                        break

                if self._is_unplayable(candidate):
                    continue

                valid = all(
                    0 <= int(b.pos.x) < self.cols and 0 <= int(b.pos.y) < self.rows
                    for b in candidate.blocks
                )
                if valid:
                    for b in candidate.blocks:
                        x = int(b.pos.x)
                        y = int(b.pos.y)
                        if base_board[y][x]:
                            valid = False
                            break
                if not valid:
                    continue

                sim_board = [row[:] for row in base_board]
                for b in candidate.blocks:
                    sim_board[int(b.pos.y)][int(b.pos.x)] = 1

                lines_cleared = sum(1 for row in sim_board if all(cell != 0 for cell in row))
                cost_now = self._cost_function(sim_board, lines_cleared, candidate)

                # Lookahead (optional, tunable weight)
                if next_shape:
                    next_score = self._evaluate_next_piece(sim_board, next_shape, candidate)
                    total_score = -cost_now +  next_score
                else:
                    total_score = -cost_now

                if total_score > best_score:
                    best_score = total_score
                    best_rotation = rotation_count
                    best_dx = dx

        if best_score == float("-inf"):
            return

        tetromino = self.game.tetromino
        rotations_needed = best_rotation
        dx_needed = best_dx

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
                dropped = True
                while dropped:
                    dropped = tetromino.move_down()
        self.last_action_time = now

    def _evaluate_next_piece(self, board, next_shape, prev_candidate=None):
        next_piece = self.Tetrominos(
            next_shape,
            pygame.sprite.Group(),
            self.game.create_new_tetromino,
            [row[:] for row in board]
        )
        shape = getattr(next_piece, "shape", None)
        if shape == "O":
            max_rotations = 1
        elif shape in ("I", "S", "Z"):
            max_rotations = 2
        else:
            max_rotations = 4

        best_score = float("-inf")
        for rotation_count in range(max_rotations):
            test_piece = self._clone_tetromino(next_piece)
            for _ in range(rotation_count):
                test_piece.rotate()

            leftmost = min(int(b.pos.x) for b in test_piece.blocks)
            rightmost = max(int(b.pos.x) for b in test_piece.blocks)
            dx_min = -leftmost
            dx_max = (self.cols - 1) - rightmost

            for dx in range(dx_min, dx_max + 1):
                candidate = self._clone_tetromino(test_piece)
                for b in candidate.blocks:
                    b.pos.x += dx

                while True:
                    collision = False
                    for b in candidate.blocks:
                        x = int(b.pos.x)
                        y = int(b.pos.y)
                        if y + 1 >= self.rows or (y + 1 >= 0 and board[y + 1][x]):
                            collision = True
                            break
                    if not collision:
                        for b in candidate.blocks:
                            b.pos.y += 1
                    else:
                        break

                if self._is_unplayable(candidate):
                    continue

                valid = all(
                    0 <= int(b.pos.x) < self.cols and 0 <= int(b.pos.y) < self.rows
                    for b in candidate.blocks
                )
                if valid:
                    for b in candidate.blocks:
                        x = int(b.pos.x)
                        y = int(b.pos.y)
                        if board[y][x]:
                            valid = False
                            break
                if not valid:
                    continue

                sim_board = [row[:] for row in board]
                for b in candidate.blocks:
                    sim_board[int(b.pos.y)][int(b.pos.x)] = 1

                lines_cleared = sum(1 for row in sim_board if all(cell != 0 for cell in row))
                score = -self._cost_function(sim_board, lines_cleared, candidate)
                if score > best_score:
                    best_score = score
        return best_score

    def _clone_tetromino(self, original):
        dummy_group = pygame.sprite.Group()
        clone = type(original)(
            original.shape,
            dummy_group,
            original.create_new_tetromino,
            [row[:] for row in original.game_data]
        )
        for i, b in enumerate(original.blocks):
            clone.blocks[i].pos = b.pos.copy()
        return clone

    def _blockades(self, board):
        rows = len(board)
        cols = len(board[0])
        blockades = 0
        for col in range(cols):
            found_hole = False
            for row in range(rows):
                if not board[row][col]:
                    found_hole = True
                elif found_hole and board[row][col]:
                    blockades += 1
        return blockades

    def _cost_function(self, board, lines_cleared=0, candidate=None):
        holes = 0
        agg_height = 0
        bumpiness = 0
        rows = len(board)
        cols = len(board[0])
        heights = [0 for _ in range(cols)]

        for col in range(cols):
            col_height = 0
            block_found = False
            for row in range(rows):
                if board[row][col]:
                    if not block_found:
                        col_height = rows - row
                        block_found = True
                    for k in range(row + 1, rows):
                        if not board[k][col]:
                            holes += 1
                    break
            heights[col] = col_height
            agg_height += col_height

        for i in range(cols - 1):
            bumpiness += abs(heights[i] - heights[i + 1])

        blockades = self._blockades(board)
        almost_full = count_almost_full_lines(board, allowed_gaps=2)
        well_col, well_depth = find_deepest_well(board)

        fills_well = False
        if candidate and well_col != -1:
            for b in candidate.blocks:
                x = int(b.pos.x)
                y = int(b.pos.y)
                if x == well_col and (y == self.rows - 1 or board[y + 1][x]):
                    fills_well = True
                    break

        if lines_cleared == 4:
            clear_bonus = 20
        elif lines_cleared == 3:
            clear_bonus = 5
        elif lines_cleared == 2:
            clear_bonus = 2
        elif lines_cleared == 1:
            clear_bonus = 0.1
        else:
            clear_bonus = 0

        cost = (
            1.2 * agg_height +
            4.0 * holes +
            1.2 * blockades +
            0.8 * bumpiness -
            0.5 * almost_full +
            (3.0 * fills_well if fills_well else 0) -
            clear_bonus
        )
        return cost
