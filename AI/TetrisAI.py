import pygame
from settings import ROWS, COLUMNS
from collections import deque

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

        # --- DFS search (brute-force) ---
        best_score = float("-inf")
        best_rotation = 0
        best_dx = 0

        for rotation_count in range(4):
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

                # Drop the candidate all the way down (even from negative y)
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

                # Check if ALL blocks are fully inside the field
                valid = all(
                    0 <= int(b.pos.x) < self.cols and 0 <= int(b.pos.y) < self.rows
                    for b in candidate.blocks
                )
                # Also check for collision in the final position
                if valid:
                    for b in candidate.blocks:
                        x = int(b.pos.x)
                        y = int(b.pos.y)
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

                if score > best_score:
                    best_score = score
                    best_rotation = rotation_count
                    best_dx = dx

        # --- BFS search (systematic state-space) ---
        bfs_result = self._bfs_search(original, base_board)
        if bfs_result is not None:
            bfs_score, bfs_rotation, bfs_dx = bfs_result
            # Choose best between DFS and BFS
            if bfs_score > best_score:
                best_score = bfs_score
                best_rotation = bfs_rotation
                best_dx = bfs_dx

        # EXECUTE the chosen move
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

        # Hard drop if at target
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

    def _bfs_search(self, original, base_board):
        # BFS node: (piece, rotation_count, dx_from_spawn)
        Node = lambda piece, rot, dx: (piece, rot, dx)
        visited = set()
        queue = deque()
        best_score = float("-inf")
        best_rotation = 0
        best_dx = 0

        # Start with all 4 rotations at spawn pos
        for rot in range(4):
            piece = self._clone_tetromino(original)
            for _ in range(rot):
                piece.rotate()
            state = (self._blocks_state(piece), rot, 0)
            queue.append((piece, rot, 0))
            visited.add(self._blocks_state(piece))

        while queue:
            piece, rot, dx = queue.popleft()
            # Try moving down until collision (simulate gravity)
            candidate = self._clone_tetromino(piece)
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

            # Validate candidate
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
            if valid:
                sim_board = [row[:] for row in base_board]
                for b in candidate.blocks:
                    sim_board[int(b.pos.y)][int(b.pos.x)] = 1
                score = -self._cost_function(sim_board)
                if score > best_score:
                    best_score = score
                    best_rotation = rot
                    best_dx = dx

            # Enqueue all possible moves: left, right, rotate
            # Move left
            piece_left = self._clone_tetromino(piece)
            for b in piece_left.blocks:
                b.pos.x -= 1
            key = self._blocks_state(piece_left)
            if key not in visited and self._valid_piece(piece_left, base_board):
                visited.add(key)
                queue.append((piece_left, rot, dx - 1))

            # Move right
            piece_right = self._clone_tetromino(piece)
            for b in piece_right.blocks:
                b.pos.x += 1
            key = self._blocks_state(piece_right)
            if key not in visited and self._valid_piece(piece_right, base_board):
                visited.add(key)
                queue.append((piece_right, rot, dx + 1))

            # Rotate
            piece_rot = self._clone_tetromino(piece)
            piece_rot.rotate()
            rot_next = (rot + 1) % 4
            key = self._blocks_state(piece_rot)
            if key not in visited and self._valid_piece(piece_rot, base_board):
                visited.add(key)
                queue.append((piece_rot, rot_next, dx))

        if best_score > float("-inf"):
            return (best_score, best_rotation, best_dx)
        else:
            return None

    def _blocks_state(self, piece):
        # Tuple of rounded (x, y) positions, sorted, uniquely identify a tetromino's arrangement
        return tuple(sorted((round(b.pos.x), round(b.pos.y)) for b in piece.blocks))

    def _valid_piece(self, piece, board):
        for b in piece.blocks:
            x = int(b.pos.x)
            y = int(b.pos.y)
            if not (0 <= x < self.cols and -4 < y < self.rows):  # Allow negative y at spawn
                return False
            if 0 <= y < self.rows and board[y][x]:
                return False
        return True

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

    def _cost_function(self, board):
        holes = 0
        blockades = 0
        agg_height = 0
        bumpiness = 0
        lines_cleared = 0
        rows = len(board)
        cols = len(board[0])
        heights = [0 for _ in range(cols)]

        for col in range(cols):
            col_height = 0
            block_found = False
            first_block_row = None
            for row in range(rows):
                if board[row][col]:
                    if not block_found:
                        col_height = rows - row
                        block_found = True
                        first_block_row = row
                    for k in range(row + 1, rows):
                        if not board[k][col]:
                            holes += 1
                    break
            heights[col] = col_height
            agg_height += col_height

            if first_block_row is not None:
                for k in range(first_block_row, rows):
                    if not board[k][col]:
                        for m in range(first_block_row, k):
                            if board[m][col]:
                                blockades += 1
                        break

        for i in range(cols - 1):
            bumpiness += abs(heights[i] - heights[i + 1])

        for row in board:
            if all(cell != 0 for cell in row):
                lines_cleared += 1

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
            1.2 * self._blockades(board) +
            0.8 * bumpiness -
            clear_bonus
        )
        return cost
