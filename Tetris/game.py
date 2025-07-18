from settings import *
from timers import Timer

#ai part
import sys
import os
sys.path.append(os.path.abspath('.'))
# from AI.TetrisAI import TetrisAI 
#ai part

#GA part
from AI.GA.tetris_ai import TetrisAI
#GA part

class Game: 
    def __init__(self, get_next_shape, update_score, get_held_shape):
        self.surface = pygame.Surface((GAME_WIDTH, GAME_HEIGHT))
        self.display_surface = pygame.display.get_surface()
        # The next two lines are for standalone only, comment or remove in tray mode:

        self.rect = self.surface.get_rect(topleft = (PADDING+SIDEBAR_WIDTH+PADDING, PADDING))

        # The next two lines are for standalone only, comment or remove in tray mode:

        self.sprites = pygame.sprite.Group()
        self.line_surface = self.surface.copy()
        self.line_surface.fill((0,255,0))
        self.line_surface.set_colorkey((0,255,0))
        self.line_surface.set_alpha(120)

        self.drop_speed = UPDATE_START_SPEED
        self.fast_drop_speed = UPDATE_START_SPEED * 0.1
        self.is_fast_drop = False
        self.hard_drop_in_progress = False
        self.current_bag = create_7bag()
        self.get_next_shape = get_next_shape
        self.get_held_shape = get_held_shape
        self.update_score = update_score
        self.is_held = False
        self.held_piece = None

        self.num_1line = 0
        self.num_2line = 0
        self.num_3line = 0
        self.num_tetris = 0

        self.game_data = [[0 for x in range(COLUMNS)] for y in range(ROWS)]
        self.tetromino = Tetrominos(
            get_next_tetromino(self.current_bag), 
            self.sprites, 
            self.create_new_tetromino, 
            self.game_data
        )
        self.timerss= {
            'vertical move':  Timer(UPDATE_START_SPEED, True, self.move_down),
            'horizontal move': Timer(MOVE_WAIT_TIME),
            'rotate': Timer(ROTATE_WAIT_TIME),
            'lock delay': Timer(LOCK_DELAY_TIME, False, self.lock_tetromino)
        }
        self.timerss['vertical move'].activate()

        self.lock_timer_active = False
        self.tetromino_touching_floor = False 

        self.current_score =  0
        self.current_level = 1
        self.current_lines = 0
        self.current_next_shape = None  # <-- Set by Main after each get_next_shape()
        self.ai = TetrisAI(self, Tetrominos)
        self.is_game_over = False

    def calculate_score(self, lines_cleared):
        self.current_lines += lines_cleared
        self.current_score += SCORE_DATA[lines_cleared] * self.current_level

        # if self.current_lines / 10 > self.current_level:
        #     self.current_level += 1
        #     level_to_frames = {
        #         1: 48, 2: 48, 3: 43, 4: 38, 5: 33, 6: 28, 7: 23, 8: 18, 9: 13,
        #         10: 8, 11: 6, 12: 5, 13: 4, 14: 4, 15: 4, 16: 3, 17: 3, 18: 3,
        #         19: 2, 20: 2, 21: 2, 22: 2, 23: 2, 24: 2, 25: 2, 26: 2, 27: 2, 28: 2, 29: 1
        #     }
        #     frames = level_to_frames.get(self.current_level, 1)
        #     base_frames = 48
        #     self.drop_speed = (frames / base_frames) * UPDATE_START_SPEED
        #     if not self.is_fast_drop:
        #         self.timerss['vertical move'].set_interval(self.drop_speed)

        self.update_score(self.current_lines, self.current_score, self.current_level)

    def hold_piece(self):
        if not self.is_held:
            if self.held_piece is None:
                self.held_piece = self.tetromino.shape
                new_shape = self.get_next_shape()
            else:
                new_shape, self.held_piece = self.held_piece, self.tetromino.shape

            self.get_held_shape(self.held_piece)
            self.is_held = True
            for block in self.tetromino.blocks:
                x, y = int(block.pos.x), int(block.pos.y)
                if 0 <= x < COLUMNS and 0 <= y < ROWS:
                    self.game_data[y][x] = 0
                block.kill()

            self.tetromino = Tetrominos(
                new_shape,
                self.sprites,
                self.create_new_tetromino,
                self.game_data
            )

    def move_down(self):
        self.tetromino.move_down()

    def perform_hard_drop(self):
        while not self.tetromino.next_move_vertical_collide(self.tetromino.blocks, 1):
            self.tetromino.move_down()
        for block in self.tetromino.blocks:
            x, y = int(block.pos.x), int(block.pos.y)
            if 0 <= x < COLUMNS and 0 <= y < ROWS:
                self.game_data[y][x] = block
        self.create_new_tetromino()
        self.timerss['vertical move'].set_interval(self.drop_speed)

    def create_new_tetromino(self):
        if self.is_game_over:
            return
        self.check_finished_rows()
        new_shape = self.get_next_shape()
        temp_tetromino = Tetrominos(
            new_shape,
            self.sprites,
            self.create_new_tetromino,
            self.game_data
        )
        for block in temp_tetromino.blocks:
            x, y = int(block.pos.x), int(block.pos.y)
            if y >= 0 and self.game_data[y][x]:
                self.is_game_over = True
                return
        self.tetromino = temp_tetromino

    def timers_update(self):
        for timerss in self.timerss.values():
            timerss.update()

    def draw_grid(self):
        for col in range(1, COLUMNS):
            x=col * CELL_SIZE
            pygame.draw.line(self.line_surface, LINE_COLOR, (x, 0), (x, self.surface.get_height()), 1)
        for row in range(1, ROWS):
            y= row * CELL_SIZE
            pygame.draw.line(self.line_surface, LINE_COLOR, (0, y), (self.surface.get_width(),y))
        self.surface.blit(self.line_surface,( 0, 0))

    def input(self):
        keys=pygame.key.get_pressed()
        if keys[pygame.K_DOWN]:
            if not self.is_fast_drop:
                self.is_fast_drop = True
                self.timerss['vertical move'].set_interval(self.fast_drop_speed)
        else:
            if self.is_fast_drop:
                self.is_fast_drop = False 
                self.timerss['vertical move'].set_interval(self.drop_speed)

        if not self.timerss['horizontal move'].active:
            if keys[pygame.K_LEFT]:
                self.tetromino.move_horizontal(-1)
                self.timerss["horizontal move"].activate()
            if keys[pygame.K_RIGHT]:
                self.tetromino.move_horizontal(1)
                self.timerss["horizontal move"].activate()

        if keys[pygame.K_SPACE]:
            if not self.hard_drop_in_progress:
                self.hard_drop_in_progress = True
                self.perform_hard_drop()
        else:
            self.hard_drop_in_progress = False

            if not self.timerss['rotate'].active:
                if keys[pygame.K_UP]:
                    self.tetromino.rotate()
                    self.timerss["rotate"].activate()
            if keys[pygame.K_c] and not self.is_held:
                self.hold_piece()
 
    def check_finished_rows(self):
        delete_rows = [i for i, row in enumerate(self.game_data) if all(row)]
        if not delete_rows:
            return
        for row_idx in delete_rows:
            for block in self.game_data[row_idx]:
                if block:
                    block.kill()
        for row_idx in sorted(delete_rows):
            for y in range(row_idx - 1, -1, -1):
                for x in range(COLUMNS):
                    block = self.game_data[y][x]
                    if block:
                        block.pos.y += 1
                        self.game_data[y + 1][x] = block
                        self.game_data[y][x] = 0
        self.game_data = [[0 for _ in range(COLUMNS)] for _ in range(ROWS)]
        for block in self.sprites:
            x, y = int(block.pos.x), int(block.pos.y)
            if 0 <= x < COLUMNS and 0 <= y < ROWS:
                self.game_data[y][x] = block
        lines = len(delete_rows)
        if lines == 1:
            self.num_1line += 1
        elif lines == 2:
            self.num_2line += 1
        elif lines == 3:
            self.num_3line += 1
        elif lines == 4:
            self.num_tetris += 1
        self.calculate_score(lines)

    def lock_tetromino(self):
        for block in self.tetromino.blocks:
            x, y = int(block.pos.x), int(block.pos.y)
            if 0 <= x < COLUMNS and 0 <= y < ROWS:
                self.game_data[y][x] = block
        self.create_new_tetromino()
        self.lock_timer_active = False

    def run(self):
        if self.is_game_over:
            return
        self.input()
        # --- AI receives safe lookahead next piece ---
        self.ai.update(next_shape=self.current_next_shape)
        self.timers_update()
        self.sprites.update()
        if self.tetromino.next_move_vertical_collide(self.tetromino.blocks, 1):
            if not self.lock_timer_active:
                self.timerss['lock delay'].activate()
                self.lock_timer_active = True
        else:
            if self.lock_timer_active:
                self.timerss['lock delay'].deactivate()
                self.lock_timer_active = False

        self.surface.fill(GRAY)
        ghost_positions = self.tetromino.get_ghost_positions()
        for pos in ghost_positions:
            ghost_rect = pygame.Rect(pos.x * CELL_SIZE, pos.y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(self.surface, (200, 200, 200), ghost_rect, 2)
        self.sprites.draw(self.surface)
        self.draw_grid()
        # The next two lines are for standalone only, comment or remove in tray mode:

        self.display_surface.blit(self.surface, self.rect.topleft)
        pygame.draw.rect(self.display_surface, LINE_COLOR, self.rect, 2, 2)

        # The next two lines are for standalone only, comment or remove in tray mode:


class Tetrominos:
    def __init__(self, shape, group, create_new_tetromino, game_data):
        self.block_positions = TETROMINOS[shape]['shape']
        self.color = TETROMINOS[shape]['color']
        self.create_new_tetromino = create_new_tetromino
        self.game_data = game_data
        self.shape = shape

        #create blocks
        self.blocks = [Block(group, pos, self.color) for pos in self.block_positions]

        self.create_new_tetromino_called = False


    def next_move_horizontal_collide(self, blocks, amount):
        collision_list = [block.horizontal_collide(int(block.pos.x + amount), self.game_data) for block in self.blocks]
        return  any(collision_list)

    def next_move_vertical_collide(self, blocks, amount):
        collision_list = [block.vertical_collide(int(block.pos.y + amount), self.game_data) for block in self.blocks]
        return True if any(collision_list) else False

    def move_horizontal(self, amount):
        if not self.next_move_horizontal_collide(self.blocks, amount):
            for block in self.blocks:
                block.pos.x += amount
            self.create_new_tetromino_called = False 


    def move_down(self):
        if not self.next_move_vertical_collide(self.blocks, 1):
            for block in self.blocks:
                block.pos.y += 1
            self.create_new_tetromino_called = False  # 🔄 Reset lock delay
        else:
            # Don't lock here — let Game handle it using lock timer
            pass


    def rotate(self):
        if self.shape == "O":
            return  # O doesn't rotate

        # 1. Choose pivot block
        pivot = self.blocks[1].pos if self.shape == "I" else self.blocks[0].pos

        # 2. Rotate all blocks around the pivot
        new_positions = [block.rotate(pivot) for block in self.blocks]

        # 3. Check for direct collision
        if self._is_valid_position(new_positions):
            for i, block in enumerate(self.blocks):
                block.pos = new_positions[i]
            self.create_new_tetromino_called = False  # 🔄 Reset lock delay
            return

        # 4. Try wall kicks
        kick_offsets = [
            (-1, 0), (1, 0), (-2, 0), (2, 0),
            (0, -1), (0, 1),
            (-1, -1), (1, -1), (-1, 1), (1, 1)
        ]

        for dx, dy in kick_offsets:
            kicked_positions = [pygame.Vector2(pos.x + dx, pos.y + dy) for pos in new_positions]
            if self._is_valid_position(kicked_positions):
                for i, block in enumerate(self.blocks):
                    block.pos = kicked_positions[i]
                self.create_new_tetromino_called = False  # 🔄 Reset lock delay
                return

        # 5. All kicks failed — cancel rotation
        return
    
    def _is_valid_position(self, positions):
        for pos in positions:
            x, y = int(pos.x), int(pos.y)
            if x < 0 or x >= COLUMNS or y >= ROWS:
                return False
            if y >= 0 and self.game_data[y][x]:  # Ignore off-screen negative y
                return False
        return True


                
    def get_ghost_positions(self):
        # Copy positions of all blocks
        ghost_blocks = [block.pos.copy() for block in self.blocks]

        while True:
            # Check if moving down would cause collision
            if any(
                b.y + 1 >= ROWS or self.game_data[int(b.y + 1)][int(b.x)]
                for b in ghost_blocks
            ):
                break  # landed
            for b in ghost_blocks:
                b.y += 1  # drop all ghost blocks by one

        return ghost_blocks



class Block(pygame.sprite.Sprite):
    def __init__(self, group, pos, color):

        #general
        super().__init__(group)
        self.image = pygame.Surface((CELL_SIZE, CELL_SIZE))
        self.image.fill(color)

    

        #position
        self.pos = pygame.Vector2(pos) + BLOCK_OFFSET
        # print(f"Block position - x: {self.pos.x}, y: {self.pos.y}")

        self.rect = self.image.get_rect(topleft = self.pos * CELL_SIZE)

    def rotate(self, pivot) :
        distance = self.pos -pivot
        rotated = distance.rotate(90)
        new_position = pivot + rotated

        return new_position

    def horizontal_collide(self, x, game_data):
        if not 0 <= x < COLUMNS:
            return True
        return bool(game_data[int(self.pos.y)][x])

    def vertical_collide(self, y, game_data):
        if y >= ROWS:
            return True
        return bool(game_data[y][int(self.pos.x)]) if y >= 0 else False
        
    def update(self):
        self.rect.topleft=self.pos*CELL_SIZE


