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
UPDATE_START_SPEED = 15 #change it to 800 for normal run
MOVE_WAIT_TIME = 150
ROTATE_WAIT_TIME = 170
BLOCK_OFFSET = pygame.Vector2((COLUMNS // 2)-1, -1)
LOCK_DELAY_TIME = 500  # in milliseconds

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

# shapes - Static rotation tables using SRS (Super Rotation System)
# Format: 'rotations': [state0, state1, state2, state3] where each state is 4 (x,y) tuples
# Coordinate system: +X is right, +Y is DOWN (Pygame standard)
# Pivot point (0,0) is consistent across all rotation states

TETROMINOS = {
    # T-piece: (0,0) is the center pivot block
    'T': {
        'rotations': [
            [(0, 0), (-1, 0), (1, 0), (0, -1)],   # State 0: flat, pointing up
            [(0, 0), (0, -1), (0, 1), (1, 0)],    # State 1: pointing right
            [(0, 0), (-1, 0), (1, 0), (0, 1)],    # State 2: flat, pointing down
            [(0, 0), (0, -1), (0, 1), (-1, 0)],   # State 3: pointing left
        ],
        'color': PURPLE
    },
    
    # O-piece: All 4 states identical (doesn't rotate visually)
    'O': {
        'rotations': [
            [(0, 0), (1, 0), (0, 1), (1, 1)],
            [(0, 0), (1, 0), (0, 1), (1, 1)],
            [(0, 0), (1, 0), (0, 1), (1, 1)],
            [(0, 0), (1, 0), (0, 1), (1, 1)],
        ],
        'color': YELLOW
    },
    
    # J-piece: (0,0) is the center pivot block
    'J': {
        'rotations': [
            [(0, 0), (-1, 0), (1, 0), (-1, -1)],  # State 0
            [(0, 0), (0, -1), (0, 1), (1, -1)],   # State 1
            [(0, 0), (-1, 0), (1, 0), (1, 1)],    # State 2
            [(0, 0), (0, -1), (0, 1), (-1, 1)],   # State 3
        ],
        'color': BLUE
    },
    
    # L-piece: (0,0) is the center pivot block
    'L': {
        'rotations': [
            [(0, 0), (-1, 0), (1, 0), (1, -1)],   # State 0
            [(0, 0), (0, -1), (0, 1), (1, 1)],    # State 1
            [(0, 0), (-1, 0), (1, 0), (-1, 1)],   # State 2
            [(0, 0), (0, -1), (0, 1), (-1, -1)],  # State 3
        ],
        'color': ORANGE
    },
    
    # I-piece: Pivot is between cells (bridge point)
    'I': {
        'rotations': [
            [(0, 0), (-1, 0), (1, 0), (2, 0)],    # State 0: Horizontal
            [(0, 0), (0, -1), (0, 1), (0, 2)],    # State 1: Vertical
            [(0, 0), (-1, 0), (1, 0), (2, 0)],    # State 2: Horizontal
            [(0, 0), (0, -1), (0, 1), (0, 2)],    # State 3: Vertical
        ],
        'color': CYAN
    },
    
    # S-piece: (0,0) is the center pivot block
    'S': {
        'rotations': [
            [(0, 0), (-1, 0), (0, -1), (1, -1)],  # State 0
            [(0, 0), (0, -1), (1, 0), (1, 1)],    # State 1
            [(0, 0), (-1, 1), (0, 1), (1, 0)],    # State 2
            [(0, 0), (-1, 0), (-1, -1), (0, 1)],  # State 3
        ],
        'color': GREEN
    },
    
    # Z-piece: (0,0) is the center pivot block
    'Z': {
        'rotations': [
            [(0, 0), (1, 0), (0, -1), (-1, -1)],  # State 0
            [(0, 0), (0, 1), (1, 0), (1, -1)],    # State 1
            [(0, 0), (-1, 0), (0, 1), (1, 1)],    # State 2
            [(0, 0), (0, -1), (-1, 0), (-1, 1)],  # State 3
        ],
        'color': RED
    }
}

# SRS (Super Rotation System) Wall Kick Tables
# Keys: (from_state, to_state) - rotation transition
# Values: List of 5 (dx, dy) offset tests to try in order

# General kick table for J, L, S, Z, T pieces
SRS_KICKS_GENERAL = {
    (0, 1): [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
    (1, 2): [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)],
    (2, 3): [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
    (3, 0): [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
    (1, 0): [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)],
    (2, 1): [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
    (3, 2): [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
    (0, 3): [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
}

# Special kick table for I piece
SRS_KICKS_I = {
    (0, 1): [(0, 0), (-2, 0), (1, 0), (-2, 1), (1, -2)],
    (1, 2): [(0, 0), (-1, 0), (2, 0), (-1, -2), (2, 1)],
    (2, 3): [(0, 0), (2, 0), (-1, 0), (2, -1), (-1, 2)],
    (3, 0): [(0, 0), (1, 0), (-2, 0), (1, 2), (-2, -1)],
    (1, 0): [(0, 0), (2, 0), (-1, 0), (2, -1), (-1, 2)],
    (2, 1): [(0, 0), (1, 0), (-2, 0), (1, 2), (-2, -1)],
    (3, 2): [(0, 0), (-2, 0), (1, 0), (-2, 1), (1, -2)],
    (0, 3): [(0, 0), (-1, 0), (2, 0), (-1, -2), (2, 1)],
}

SCORE_DATA = {1: 40, 2: 100, 3: 300, 4: 1200}

TETROMINOS_WEIGHTS = {
    'T': 14.6,
    'O': 14.2,
    'J': 14.3,
    'L': 13.9,
    'I': 13.9,
    'S': 14.7,
    'Z': 14.3
}


#pseudo random weighted bags
# def create_weighted_bag():
#     """Creates a weighted bag for Tetrominoes based on their weights, ensuring random distribution."""
#     bag = random.choices(
#         population=list(TETROMINOS_WEIGHTS.keys()),  # Tetromino names
#         weights=list(TETROMINOS_WEIGHTS.values()),  # Corresponding weights
#         k=14  # Choose a moderate number for the bag size (you can adjust this)
#     )
#     random.shuffle(bag)  # Shuffle to randomize the order
#     return bag

# def get_next_tetromino(bag, recent_shapes=[], max_streak=2):
#     """Fetches the next Tetromino and prevents more than `max_streak` consecutive repeats."""
#     if len(bag) == 0:  # If the bag is empty, refill it
#         bag[:] = create_weighted_bag()  # Refill the bag

#     # Select a pseudorandom piece from the bag based on weighted distribution
#     next_piece = random.choices(
#         population=list(TETROMINOS_WEIGHTS.keys()), 
#         weights=list(TETROMINOS_WEIGHTS.values()),
#         k=1
#     )[0]

#     # Ensure no streak of `max_streak` consecutive pieces
#     while len(recent_shapes) >= max_streak and all(shape == next_piece for shape in recent_shapes[-max_streak:]):
#         # Reshuffle the remaining bag if a streak of `max_streak` occurs
#         random.shuffle(bag)
#         next_piece = random.choices(
#             population=list(TETROMINOS_WEIGHTS.keys()), 
#             weights=list(TETROMINOS_WEIGHTS.values()), 
#             k=1
#         )[0]

#     # Add the piece to recent history
#     recent_shapes.append(next_piece)

#     # Keep the recent shapes list size within `max_streak`
#     if len(recent_shapes) > max_streak:
#         recent_shapes.pop(0)

#     return next_piece


# # Initialize the bag with weighted tetrominoes
# current_bag = create_weighted_bag()

def create_7bag():
    """Creates a fair 7-bag of tetromino names, each appearing exactly once, shuffled."""
    bag = list(TETROMINOS.keys())
    random.shuffle(bag)
    return bag

def get_next_tetromino(bag):
    """
    Fetches the next tetromino from the bag.
    Refills and reshuffles the bag when empty.
    Returns the name as before ('I', 'O', etc).
    """
    if not bag:
        bag[:] = create_7bag()
    return bag.pop()

# Initialize the bag as usual
current_bag = create_7bag()