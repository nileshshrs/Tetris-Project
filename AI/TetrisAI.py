import pygame
from settings import ROWS, COLUMNS

class TetrisAI:
    def __init__(self, game):
        self.game = game
        self.last_action_time = 0
        self.delay = 200  # ms between AI moves
        self.rows = ROWS
        self.cols = COLUMNS

    def update(self):
        if self.game.is_game_over or not self.game.tetromino:
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

        for rotation_count in range(4):
            test_piece = self._clone_tetromino(original)
            for _ in range(rotation_count):
                test_piece.rotate()

            # Get all horizontal positions where the piece is in bounds
            leftmost = min(int(b.pos.x) for b in test_piece.blocks)
            rightmost = max(int(b.pos.x) for b in test_piece.blocks)
            dx_min = -leftmost
            dx_max = (self.cols - 1) - rightmost

            for dx in range(dx_min, dx_max + 1):
                candidate = self._clone_tetromino(test_piece)
                for b in candidate.blocks:
                    b.pos.x += dx

                # Drop the candidate all the way down
                drop_ok = True
                while drop_ok:
                    for b in candidate.blocks:
                        x = int(b.pos.x)
                        y = int(b.pos.y)
                        if y + 1 >= self.rows or base_board[y + 1][x]:
                            drop_ok = False
                            break
                    if drop_ok:
                        for b in candidate.blocks:
                            b.pos.y += 1

                # Check for out-of-bounds (defensive, should never happen)
                valid = True
                for b in candidate.blocks:
                    x = int(b.pos.x)
                    y = int(b.pos.y)
                    if x < 0 or x >= self.cols or y < 0 or y >= self.rows:
                        valid = False
                        break
                    if base_board[y][x]:
                        valid = False
                        break
                if not valid:
                    continue

                # Lock the piece into the board
                sim_board = [row[:] for row in base_board]
                for b in candidate.blocks:
                    sim_board[int(b.pos.y)][int(b.pos.x)] = 1

                score = -self._cost_function(sim_board)  # Lower cost is better
                # Uncomment for debugging:
                # print(f"rot={rotation_count}, dx={dx}, score={score}")

                if score > best_score:
                    best_score = score
                    best_rotation = rotation_count
                    best_dx = dx

        # Apply best move to the real piece
        if best_score > float("-inf"):
            for _ in range(best_rotation):
                self.game.tetromino.rotate()
            if best_dx > 0:
                for _ in range(best_dx):
                    self.game.tetromino.move_horizontal(+1)
            elif best_dx < 0:
                for _ in range(-best_dx):
                    self.game.tetromino.move_horizontal(-1)

        self.last_action_time = now

    def _clone_tetromino(self, original):
        dummy_group = pygame.sprite.Group()
        clone = type(original)(
            shape=original.shape,
            group=dummy_group,
            create_new_tetromino=original.create_new_tetromino,
            game_data=original.game_data
        )
        for i, b in enumerate(original.blocks):
            clone.blocks[i].pos = b.pos.copy()
        return clone

    def _cost_function(self, board):
        # This is adapted from your Greedy_AI reference: lower cost is better
        holes = 0
        agg_height = 0
        bumpiness = 0
        lines_cleared = 0
        rows = len(board)
        cols = len(board[0])
        heights = [0 for _ in range(cols)]

        # Heights and holes
        for col in range(cols):
            col_height = 0
            block_found = False
            for row in range(rows):
                if board[row][col]:
                    if not block_found:
                        col_height = rows - row
                        block_found = True
                    # Count holes below the first filled block
                    for k in range(row + 1, rows):
                        if not board[k][col]:
                            holes += 1
                    break
            heights[col] = col_height
            agg_height += col_height

        # Bumpiness
        for i in range(cols - 1):
            bumpiness += abs(heights[i] - heights[i + 1])

        # Line clears
        for row in board:
            if all(cell != 0 for cell in row):
                lines_cleared += 1

        # Heuristic weights (reference AI style)
        cost = (
            0.5 * agg_height +
            0.35 * holes +
            0.18 * bumpiness -
            0.76 * lines_cleared
        )

        return cost
