from settings import *
from timers import Timer


class Game: 
    def __init__(self, get_next_shape, update_score):
        self.surface = pygame.Surface((GAME_WIDTH, GAME_HEIGHT))
        self.display_surface = pygame.display.get_surface()
        self.rect = self.surface.get_rect(topleft = (SIDEBAR_WIDTH+PADDING, PADDING))
        self.sprites = pygame.sprite.Group()
        #lines transparency
        self.line_surface = self.surface.copy()
        self.line_surface.fill((0,255,0))
        self.line_surface.set_colorkey((0,255,0))
        self.line_surface.set_alpha(120)

        self.drop_speed = UPDATE_START_SPEED
        self.fast_drop_speed = UPDATE_START_SPEED * 0.1  # Speed when the down key is pressed
        self.is_fast_drop = False  # Flag to track down key press
        self.hard_drop_in_progress = False
        self.current_bag = create_weighted_bag()
        self.get_next_shape = get_next_shape
        
        self.update_score = update_score

        #tetromino
        self.game_data = [[0 for x in range(COLUMNS)] for y in range(ROWS)]
        self.tetromino = Tetrominos(
            get_next_tetromino(self.current_bag), 
            self.sprites, 
            self.create_new_tetromino, 
            self.game_data)
        # timer
        self.timerss= {
            'vertical move':  Timer(UPDATE_START_SPEED, True, self.move_down),
            'horizontal move': Timer(MOVE_WAIT_TIME),
            'rotate': Timer(ROTATE_WAIT_TIME)
        }
        self.timerss['vertical move'].activate()

        self.current_score =  0
        self.current_level = 1
        self.current_lines = 0

    def calculate_score(self, lines_cleared):
        self.current_lines += lines_cleared
        print(f'Lines cleared: {self.current_lines}')
        self.current_score += SCORE_DATA[lines_cleared] * self.current_level
        print(f'Score: {self.current_score}') 

        # Every 10 lines, increase the level by 1
        if self.current_lines / 10 > self.current_level:
            self.current_level += 1
            print(f'Level: {self.current_level}')

        self.update_score(self.current_lines, self.current_score, self.current_level)

    def move_down(self):
        #print("timers")
        self.tetromino.move_down()

    def perform_hard_drop(self):
        # Drop the tetromino until it cannot move further
        while not self.tetromino.next_move_vertical_collide(self.tetromino.blocks, 1):
            self.tetromino.move_down()
        
        # Lock the tetromino in place directly in this method
        for block in self.tetromino.blocks:
            x, y = int(block.pos.x), int(block.pos.y)
            if 0 <= x < COLUMNS and 0 <= y < ROWS:
                self.game_data[y][x] = block
            # else:
               # print(f"Block position out of bounds - x: {x}, y: {y}")

        # Create a new tetromino
        self.create_new_tetromino()
    #create new tetromino
    def create_new_tetromino(self):
        self.check_finished_rows()
        self.tetromino= Tetrominos(
            self.get_next_shape(), 
            self.sprites, 
            self.create_new_tetromino,
            self.game_data)
        
  
    def timers_update(self):
       for timerss in self.timerss.values():
           timerss.update()
    
    def draw_grid(self):

        for col in range(1, COLUMNS):
            x=col * CELL_SIZE
            pygame.draw.line(self.line_surface, LINE_COLOR, (x, 0), (x, self.surface.get_height()), 1)

        for row in range(1, ROWS)   :
            y= row * CELL_SIZE
            pygame.draw.line(self.line_surface, LINE_COLOR, (0, y), (self.surface.get_width(),y))
        self.surface.blit(self.line_surface,( 0, 0))

    def input(self):
        keys=pygame.key.get_pressed()
        if keys[pygame.K_DOWN]:
            if not self.is_fast_drop:
                # Change the vertical movement timer to fast drop speed
                self.is_fast_drop = True
                self.timerss['vertical move'].set_interval(self.fast_drop_speed)
        else:
            if self.is_fast_drop:
                # Revert to original drop speed if down key is not pressed
                self.is_fast_drop = False 
                self.timerss['vertical move'].set_interval(self.drop_speed)
        

        if not self.timerss['horizontal move'].active:
            if keys[pygame.K_LEFT]:
                #print("left")
                self.tetromino.move_horizontal(-1)
                self.timerss["horizontal move"].activate()

            if keys[pygame.K_RIGHT]:
                #print("left")
                self.tetromino.move_horizontal(1)
                self.timerss["horizontal move"].activate()

        if keys[pygame.K_SPACE]:
            if not self.hard_drop_in_progress:
                self.hard_drop_in_progress = True
                self.perform_hard_drop()
        else:
            self.hard_drop_in_progress = False

        if not self.timerss['rotate'].active:
            if keys[pygame.K_c] or keys[pygame.K_UP]:
                self.tetromino.rotate()
                self.timerss["rotate"].activate()
        
 

    def check_finished_rows(self):

            # get the full row indexes 
            delete_rows = []
            for i, row in enumerate(self.game_data):
                if all(row):
                    delete_rows.append(i)

            if delete_rows:
                for delete_row in delete_rows:

                    # delete full rows
                    for block in self.game_data[delete_row]:
                        block.kill()

                    # move down blocks
                    for row in self.game_data:
                        for block in row:
                            if block and block.pos.y < delete_row:
                                block.pos.y += 1

                # rebuild the game data 
                self.game_data = [[0 for x in range(COLUMNS)] for y in range(ROWS)]
                for block in self.sprites:
                    self.game_data[int(block.pos.y)][int(block.pos.x)] = block

                #update score
                self.calculate_score(len(delete_rows))
			    


    def run(self):

        #update 
        self.input()
        self.timers_update()
        self.sprites.update()
        #draw ink
        self.surface.fill(GRAY)
        self.sprites.draw(self.surface)
        self.draw_grid()
        self.display_surface.blit(self.surface, (SIDEBAR_WIDTH+PADDING, PADDING)) #block image transfer
        pygame.draw.rect(self.display_surface, LINE_COLOR, self.rect, 2, 2)


class Tetrominos:
    def __init__(self, shape, group, create_new_tetromino, game_data):
        self.block_positions = TETROMINOS[shape]['shape']
        self.color = TETROMINOS[shape]['color']
        self.create_new_tetromino = create_new_tetromino
        self.game_data = game_data
        self.shape = shape

        #create blocks
        self.blocks = [Block(group, pos, self.color) for pos in self.block_positions]

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

    def move_down(self):

        if not self.next_move_vertical_collide(self.blocks, 1):
            for block in self.blocks:
                block.pos.y += 1
        else:
            for block in self.blocks:
                self.game_data[int(block.pos.y)][int(block.pos.x)] = block
            self.create_new_tetromino()

    def rotate(self):
        if self.shape != "O":  # O shape doesn't rotate
            if self.shape == "I":
                pivot = self.blocks[1].pos  # Use the second block as pivot for "I"
            else:
                pivot = self.blocks[0].pos  # Default pivot for other shapes

            # Step 1: Default rotation (without collision handling)
            new_positions = [block.rotate(pivot) for block in self.blocks]

            # Step 2: Check if rotation causes a collision
            collision_detected = False
            for pos in new_positions:
                x, y = int(pos.x), int(pos.y)
                if y >= ROWS or x < 0 or x >= COLUMNS or (y >= 0 and self.game_data[y][x]):
                    collision_detected = True
                    break

            # Step 3: If no collision, apply the rotation
            if not collision_detected:
                for i, block in enumerate(self.blocks):
                    block.pos = new_positions[i]
            else:
                # Handle collisions (wall kicks)
                shifted_positions = None
                if self.shape == "I":
                    wall_kicks = [-2, -1, 1, 2]  # I needs bigger shifts
                elif self.shape == "L"  :
                    # L and J shapes have a specific kick pattern
                    wall_kicks = [-1, 1] 
                elif self.shape == "J":
                    wall_kicks = [2, -2]
                else:
                    wall_kicks = [-1, 1]  # Default shift pattern for other shapes

                for dx in wall_kicks:
                    temp_positions = [pygame.Vector2(pos.x + dx, pos.y) for pos in new_positions]

                    # Check if the shifted positions are valid
                    valid_shift = True
                    for pos in temp_positions:
                        x, y = int(pos.x), int(pos.y)
                        if y >= ROWS or x < 0 or x >= COLUMNS or (y >= 0 and self.game_data[y][x]):
                            valid_shift = False
                            break

                    if valid_shift:
                        shifted_positions = temp_positions
                        break

                # Apply the shift if valid, otherwise cancel rotation
                if shifted_positions:
                    for i, block in enumerate(self.blocks):
                        block.pos = shifted_positions[i]
                else:
                    return  # Cancel the rotation



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

    def horizontal_collide(self, x, game_data ):
        if not 0 <= x < COLUMNS:
            return True
        if game_data[int(self.pos.y)][x]:
            return True
    
    def vertical_collide(self, y, game_data):
        if y >= ROWS:
            return True
        if y >= 0 and game_data[y][int(self.pos.x)]:
            return True
        
    def update(self):
        self.rect.topleft=self.pos*CELL_SIZE


