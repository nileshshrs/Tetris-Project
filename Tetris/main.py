from settings import *
from sys import exit

# Components
from game import Game
from score import Score
from lines import Lines  # Fixed: Importing Lines
from preview import Preview
from held import Held

class Main:
    def __init__(self):
        # General setup
        pygame.init()
        self.display_surface = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        pygame.display.set_caption("TETRIS")

        # Components
        self.bag = create_weighted_bag()
        self.next_shapes = [get_next_tetromino(self.bag) for _ in range(3)]

        self.game = Game(self.get_next_shape, self.update_score, self.get_held_shape)
        self.score = Score()
        self.lines = Lines()  # Fixed: Initialized Lines component
        self.held = Held()
        self.preview = Preview()

    def update_score(self, lines, score, levels):
        """Updates both Score and Lines components."""
        self.score.score = score
        self.score.levels = levels  # Score no longer displays levels, but keeping for future use
        self.lines.lines = lines
        self.lines.levels = levels

    def get_next_shape(self):
            """Fetches the next shape from the queue, refilling when needed."""
            next_piece = self.next_shapes.pop(0)  # Take the first piece
            self.next_shapes.append(get_next_tetromino(self.bag))  # Add a new one to maintain size 3
            self.game.is_held = False  # Reset hold status for the new piece
            return next_piece
    def get_held_shape(self, shape):
        self.held.held_shape = shape  # Update the held shape in the Held component

    def run(self):
        """Main game loop."""
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()
                    
            # Display
            self.display_surface.fill(GRAY)

            # Components
            self.game.run()
            self.score.run()
            self.lines.run()  # Fixed: Running Lines component
            self.preview.run(self.next_shapes)
            self.held.run()

            # Update the game
            pygame.display.update()
            self.clock.tick()

if __name__ == "__main__":
    main = Main()
    main.run()
