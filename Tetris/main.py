from settings import *
from sys import exit

# Components
from game import Game
from score import Score
from lines import Lines  # Fixed: Importing Lines
from preview import Preview

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

        self.game = Game(self.get_next_shape, self.update_score)
        self.score = Score()
        self.lines = Lines()  # Fixed: Initialized Lines component
        self.preview = Preview()

    def update_score(self, lines, score, levels):
        """Updates both Score and Lines components."""
        self.score.score = score
        self.score.levels = levels  # Score no longer displays levels, but keeping for future use
        self.lines.lines = lines
        self.lines.levels = levels

    def get_next_shape(self):
        """Returns the next Tetromino shape and updates the queue."""
        next_shape = self.next_shapes.pop(0)
        self.next_shapes.append(get_next_tetromino(self.bag))  # Add a new shape from the bag to the end
        return next_shape

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

            # Update the game
            pygame.display.update()
            self.clock.tick()

if __name__ == "__main__":
    main = Main()
    main.run()
