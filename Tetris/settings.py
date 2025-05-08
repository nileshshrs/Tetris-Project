import pygame 
import random


# Game size 
COLUMNS = 10
ROWS = 20
CELL_SIZE = 40
GAME_WIDTH, GAME_HEIGHT = COLUMNS * CELL_SIZE, ROWS * CELL_SIZE

# side bar size 
SIDEBAR_WIDTH = 200
PREVIEW_HEIGHT_FRACTION = 0.7
SCORE_HEIGHT_FRACTION = 1 - PREVIEW_HEIGHT_FRACTION

# window
PADDING = 20
WINDOW_WIDTH = PADDING * 3 + SIDEBAR_WIDTH + GAME_WIDTH + SIDEBAR_WIDTH + PADDING * 3
WINDOW_HEIGHT = GAME_HEIGHT + PADDING * 2

# game behaviour 
UPDATE_START_SPEED = 800
MOVE_WAIT_TIME = 150
ROTATE_WAIT_TIME = 170
BLOCK_OFFSET = pygame.Vector2((COLUMNS // 2)-1, -1)

# Colors 
YELLOW = '#f1e60d'
RED = '#e51b20'
BLUE = '#204b9b'
GREEN = '#65b32e'
PURPLE = '#7b217f'
CYAN = '#6cc6d9'
ORANGE = '#f07e13'
GRAY = '#1C1C1C'
LINE_COLOR = '#FFFFFF'

colors = [YELLOW, RED, BLUE, GREEN, PURPLE, CYAN, ORANGE]

# shapes
TETROMINOS = {
    'T': {'shape': [(0,0), (-1,0), (1,0), (0,-1)], 'color': PURPLE },
    'O': {'shape': [(0,0), (0,-1), (1,0), (1,-1)], 'color': YELLOW},
    'J': {'shape': [(0,1), (1,1), (2,1), (2,0)], 'color': BLUE},
    'L': {'shape': [(0,0), (1,0), (2,0), (2,1)], 'color': ORANGE},
    'I': {'shape': [(0,0), (1,0), (2,0), (3,0)], 'color': CYAN},
    'S': {'shape': [(0,0), (-1,0), (0,-1), (1,-1)], 'color': GREEN},
    'Z': {'shape': [(0,0), (1,0), (0,-1), (-1,-1)], 'color': RED}
}

SCORE_DATA = {1: 100, 2: 300, 3: 500, 4: 1200}

TETROMINOS_WEIGHTS = {
    'T': 14.6,
    'O': 14.2,
    'J': 14.3,
    'L': 13.9,
    'I': 13.9,
    'S': 14.7,
    'Z': 14.3
}

# def create_weighted_bag():
#     bag = []
#     for tetromino, weight in TETROMINOS_WEIGHTS.items():
#         # Calculate the number of times to add each tetromino based on its weight
#         num_items = int(weight * 100)  # Scale weights for practical use
#         bag.extend([tetromino] * num_items)
#     random.shuffle(bag)  # Shuffle to randomize the order
#     return bag

# def get_next_tetromino(bag):
#     if not bag:
#         bag[:] = create_weighted_bag()  # Refill and shuffle the bag if empty
#     return bag.pop()


def create_weighted_bag():
    """Creates a weighted bag for Tetrominoes based on their weights, ensuring random distribution."""
    bag = random.choices(
        population=list(TETROMINOS_WEIGHTS.keys()),  # Tetromino names
        weights=list(TETROMINOS_WEIGHTS.values()),  # Corresponding weights
        k=14  # Choose a moderate number for the bag size (you can adjust this)
    )
    random.shuffle(bag)  # Shuffle to randomize the order
    return bag

def get_next_tetromino(bag, recent_shapes=[], max_streak=2):
    """Fetches the next Tetromino and prevents more than `max_streak` consecutive repeats."""
    if len(bag) == 0:  # If the bag is empty, refill it
        bag[:] = create_weighted_bag()  # Refill the bag

    # Select a pseudorandom piece from the bag based on weighted distribution
    next_piece = random.choices(
        population=list(TETROMINOS_WEIGHTS.keys()), 
        weights=list(TETROMINOS_WEIGHTS.values()),
        k=1
    )[0]

    # Ensure no streak of `max_streak` consecutive pieces
    while len(recent_shapes) >= max_streak and all(shape == next_piece for shape in recent_shapes[-max_streak:]):
        # Reshuffle the remaining bag if a streak of `max_streak` occurs
        random.shuffle(bag)
        next_piece = random.choices(
            population=list(TETROMINOS_WEIGHTS.keys()), 
            weights=list(TETROMINOS_WEIGHTS.values()), 
            k=1
        )[0]

    # Add the piece to recent history
    recent_shapes.append(next_piece)

    # Keep the recent shapes list size within `max_streak`
    if len(recent_shapes) > max_streak:
        recent_shapes.pop(0)

    return next_piece


# Initialize the bag with weighted tetrominoes
current_bag = create_weighted_bag()

