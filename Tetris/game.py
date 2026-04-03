from settings import *
from timers import Timer
from core import TetrisCore

class Game: 
    def __init__(self, get_next_shape, update_score, get_held_shape, initial_shape,
                ai_class=None, ai_kwargs=None):
        self.surface = pygame.Surface((GAME_WIDTH, GAME_HEIGHT))
        self.display_surface = pygame.display.get_surface()
        self.rect = self.surface.get_rect(topleft = (PADDING+SIDEBAR_WIDTH+PADDING, PADDING))

        self.bg_surface = pygame.Surface((GAME_WIDTH, GAME_HEIGHT))
        self.bg_surface.fill(GRAY)

        self.line_surface = self.surface.copy()
        self.line_surface.fill((0,255,0))
        self.line_surface.set_colorkey((0,255,0))
        self.line_surface.set_alpha(120)
        
        # Bake grid lines once
        for col in range(1, COLUMNS):
            x = col * CELL_SIZE
            pygame.draw.line(self.line_surface, LINE_COLOR, (x, 0), (x, self.surface.get_height()), 1)
        for row in range(1, ROWS):
            y = row * CELL_SIZE
            pygame.draw.line(self.line_surface, LINE_COLOR, (0, y), (self.surface.get_width(), y), 1)

        self.drop_speed = UPDATE_START_SPEED
        self.fast_drop_speed = UPDATE_START_SPEED * 0.1
        self.is_fast_drop = False
        self.hard_drop_in_progress = False

        self.get_next_shape = get_next_shape
        self.get_held_shape = get_held_shape
        self.update_score = update_score
        self.is_held = False
        self.held_piece = None
        self.current_move_dir = 0
        self.lock_move_count = 0

        self.num_1line = 0
        self.num_2line = 0
        self.num_3line = 0
        self.num_tetris = 0

        self.game_data = [[0 for x in range(COLUMNS)] for y in range(ROWS)]
        self.tetromino = Tetrominos(
            initial_shape,
            self.game_data
        )
        self.timerss= {
            'vertical move':  Timer(UPDATE_START_SPEED, True, self.move_down),
            'horizontal move': Timer(DAS_DELAY),
            'rotate': Timer(ROTATE_WAIT_TIME),
            'lock delay': Timer(LOCK_DELAY_TIME, False, self.lock_tetromino)
        }
        self.timerss['vertical move'].activate()

        self.lock_timer_active = False


        self.current_score =  0
        self.current_level = 1
        self.current_lines = 0
        self.current_next_shape = None  # <-- Set by Main after each get_next_shape()
        
        # Configurable AI
        if ai_class is None:
            from AI.TetrisAI import TetrisAI as ai_class
        ai_kwargs = ai_kwargs or {}
        self.ai = ai_class(self, **ai_kwargs)
        
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

            self.tetromino = Tetrominos(
                new_shape,
                self.game_data
            )
            self.lock_move_count = 0
            self.timerss['lock delay'].deactivate()
            self.lock_timer_active = False
            self.lock_move_count = 0

    def _on_movement(self):
        if self.lock_timer_active and self.lock_move_count < 15:
            self.timerss['lock delay'].activate()
            self.lock_move_count += 1

    def move_down(self):
        self.tetromino.move_down()

    def perform_hard_drop(self):
        while self.tetromino.move_down():
            pass
        self.lock_tetromino()
        self.timerss['vertical move'].set_interval(self.drop_speed)
        self.is_fast_drop = False

    def create_new_tetromino(self):
        if self.is_game_over:
            return
        self.check_finished_rows()
        new_shape = self.get_next_shape()
        temp_tetromino = Tetrominos(
            new_shape,
            self.game_data
        )

        # Game-over check
        if TetrisCore.is_game_over(self.game_data, new_shape, 0, int(temp_tetromino.pivot.x), int(temp_tetromino.pivot.y)):
            self.is_game_over = True
            return
        self.tetromino = temp_tetromino
        self.lock_move_count = 0

    def timers_update(self):
        for timerss in self.timerss.values():
            timerss.update()

    def draw_grid(self):
        self.surface.blit(self.line_surface, (0, 0))

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

        # Horizontal Movement (DAS & ARR)
        move_dir = 0
        if keys[pygame.K_LEFT]:
            move_dir = -1
        elif keys[pygame.K_RIGHT]:
            move_dir = 1
            
        if move_dir != 0:
            if self.current_move_dir != move_dir:
                # Initial press
                self.current_move_dir = move_dir
                if self.tetromino.move_horizontal(move_dir):
                    self._on_movement()
                self.timerss["horizontal move"].set_interval(DAS_DELAY)
                self.timerss["horizontal move"].activate()
            else:
                # Held
                if not self.timerss["horizontal move"].active:
                    if self.tetromino.move_horizontal(move_dir):
                        self._on_movement()
                    self.timerss["horizontal move"].set_interval(ARR_SPEED)
                    self.timerss["horizontal move"].activate()
        else:
            self.current_move_dir = 0
            self.timerss["horizontal move"].deactivate()

        if keys[pygame.K_SPACE]:
            if not self.hard_drop_in_progress:
                self.hard_drop_in_progress = True
                self.perform_hard_drop()
        else:
            self.hard_drop_in_progress = False

        if not self.timerss['rotate'].active:
            if keys[pygame.K_UP]:
                if self.tetromino.rotate(clockwise=True):
                    self._on_movement()
                self.timerss["rotate"].activate()
            elif keys[pygame.K_z]:
                if self.tetromino.rotate(clockwise=False):
                    self._on_movement()
                self.timerss["rotate"].activate()
                
        if keys[pygame.K_c] and not self.is_held:
            self.hold_piece()
 
    def check_finished_rows(self):
        delete_rows = [i for i, row in enumerate(self.game_data) if all(row)]
        if not delete_rows:
            return

        lines = len(delete_rows)
        
        # New rebuild logic for color-based game_data
        new_game_data = [[0 for _ in range(COLUMNS)] for _ in range(lines)]
        for i, row in enumerate(self.game_data):
            if i not in delete_rows:
                new_game_data.append(row[:])
        self.game_data = new_game_data

        # Re-bake the bg_surface
        self.bg_surface.fill(GRAY)
        for y, row in enumerate(self.game_data):
            for x, color in enumerate(row):
                if color != 0:
                    pygame.draw.rect(self.bg_surface, color, (x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE))

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
        px = int(self.tetromino.pivot.x)
        py = int(self.tetromino.pivot.y)
        cells = TetrisCore.get_piece_cells(self.tetromino.shape, self.tetromino.rotation_index, px, py)
        
        is_completely_above = True
        for x, y in cells:
            if y >= 0:
                is_completely_above = False
            if 0 <= x < COLUMNS and 0 <= y < ROWS:
                self.game_data[y][x] = self.tetromino.color
                # Bake to bg_surface
                pygame.draw.rect(self.bg_surface, self.tetromino.color, (x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE))
        
        if is_completely_above:
            self.is_game_over = True
            return
            
        self.create_new_tetromino()
        self.lock_timer_active = False



    def run(self):
        if self.is_game_over:
            return
        self.input()
        # --- AI receives safe lookahead next piece + hold info ---
        self.ai.update(
            next_shape=self.current_next_shape,
            held_piece=self.held_piece,
            is_held=self.is_held
        )
        self.timers_update()

        # --- Collision detection ---
        collide = not TetrisCore.is_valid_pos(
            self.game_data, self.tetromino.shape, self.tetromino.rotation_index, 
            int(self.tetromino.pivot.x), int(self.tetromino.pivot.y + 1)
        )

        if collide:
            if not self.lock_timer_active:
                self.timerss['lock delay'].activate()
                self.lock_timer_active = True
        else:
            if self.lock_timer_active:
                self.timerss['lock delay'].deactivate()
                self.lock_timer_active = False

        self.surface.fill(GRAY)
        self.surface.blit(self.bg_surface, (0, 0))

        ghost_positions = self.tetromino.get_ghost_positions()
        for x, y in ghost_positions:
            if y >= 0:
                pygame.draw.rect(self.surface, (200, 200, 200), (x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE), 2)
            
        # Draw active piece
        px = int(self.tetromino.pivot.x)
        py = int(self.tetromino.pivot.y)
        cells = TetrisCore.get_piece_cells(self.tetromino.shape, self.tetromino.rotation_index, px, py)
        for x, y in cells:
            if y >= 0: # Only draw if on screen
                pygame.draw.rect(self.surface, self.tetromino.color, (x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE))

        self.draw_grid()

        self.display_surface.blit(self.surface, self.rect.topleft)
        pygame.draw.rect(self.display_surface, LINE_COLOR, self.rect, 2, 2)



class Tetrominos:
    def __init__(self, shape, game_data):
        self.shape = shape
        self.color = TETROMINOS[shape]['color']
        self.game_data = game_data
        
        # Static rotation system
        self.rotation_index = 0  # Current rotation state (0-3)
        
        # Pivot position (reference point for blocks)
        self.pivot = pygame.Vector2(BLOCK_OFFSET)
        
    def move_horizontal(self, amount):
        if TetrisCore.is_valid_pos(self.game_data, self.shape, self.rotation_index, int(self.pivot.x + amount), int(self.pivot.y)):
            self.pivot.x += amount
            return True
        return False

    def move_down(self):
        if TetrisCore.is_valid_pos(self.game_data, self.shape, self.rotation_index, int(self.pivot.x), int(self.pivot.y + 1)):
            self.pivot.y += 1
            return True
        return False

    def rotate(self, clockwise=True):
        """Rotate using static SRS tables with wall kicks via TetrisCore."""
        if self.shape == "O":
            return False  # O doesn't rotate
        
        success, new_rot, new_x, new_y = TetrisCore.try_rotate(
            self.game_data, self.shape, self.rotation_index, 
            int(self.pivot.x), int(self.pivot.y), clockwise
        )
        if success:
            self.rotation_index = new_rot
            self.pivot.x = new_x
            self.pivot.y = new_y
            return True
        return False

    def get_ghost_positions(self):
        """Calculate ghost piece landing positions using TetrisCore."""
        px = int(self.pivot.x)
        py = int(self.pivot.y)
        drop_y = TetrisCore.hard_drop_y(
            self.game_data, self.shape, self.rotation_index, px, py
        )
        return TetrisCore.get_piece_cells(
            self.shape, self.rotation_index, px, drop_y
        )
