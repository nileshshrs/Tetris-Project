from settings import *
from sys import exit
import time
import pygame

# Components
from game import Game
from score import Score
from lines import Lines
from preview import Preview
from held import Held

class Main:
    def __init__(self):
        # General setup
        pygame.init()
        self.display_surface = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        pygame.display.set_caption("TETRIS")

        # Piece bag and preview queue
        self.bag = create_weighted_bag()
        self.next_shapes = [get_next_tetromino(self.bag) for _ in range(3)]

        # Game and UI components
        self.game = Game(self.get_next_shape, self.update_score, self.get_held_shape)
        self.score = Score()
        self.lines = Lines()
        self.held = Held()
        self.preview = Preview()

        # --- AI lookahead support: always up-to-date next shape ---
        self.game.current_next_shape = self.next_shapes[0]

    def update_score(self, lines, score, levels):
        self.score.score = score
        self.score.levels = levels
        self.lines.lines = lines
        self.lines.levels = levels

    def get_next_shape(self):
        # --- Always update next_shapes and current_next_shape ---
        next_piece = self.next_shapes.pop(0)
        self.next_shapes.append(get_next_tetromino(self.bag))
        self.game.is_held = False
        self.game.current_next_shape = self.next_shapes[0]
        return next_piece

    def get_held_shape(self, shape):
        self.held.held_shape = shape

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()

            self.display_surface.fill(GRAY)

            if self.game.is_game_over:
                if self.score.frozen_time is None:
                    self.score.frozen_time = int(time.time() - self.score.start_time)
                self.score.run()
                self.lines.run()
                self.preview.run(self.next_shapes)
                self.held.run()

                # Optional: Show "Game Over"
                font = pygame.font.SysFont("arial", 48, bold=True)
                text = font.render("GAME OVER", True, (255, 0, 0))
                text_rect = text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
                self.display_surface.blit(text, text_rect)

                pygame.display.update()
                self.clock.tick(60)
                continue

            # --- Normal game loop ---
            self.game.run()
            self.score.run()
            self.lines.run()
            self.preview.run(self.next_shapes)
            self.held.run()

            pygame.display.update()
            self.clock.tick(60)

if __name__ == "__main__":
    main = Main()
    main.run()
