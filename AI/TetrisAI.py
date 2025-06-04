# tetris_ai.py
import random
import pygame

class TetrisAI:
    def __init__(self, game):
        self.game = game
        self.last_action_time = 0
        self.delay = 1000  # milliseconds between moves

    def update(self):
        if self.game.is_game_over:
            return

        current_time = pygame.time.get_ticks()
        if current_time - self.last_action_time < self.delay:
            return

        tetro = self.game.tetromino

        # 1. Randomly rotate 0–3 times
        for _ in range(random.randint(0, 3)):
            tetro.rotate()

        # 2. Random horizontal movement (up to 5 steps)
        moves = random.randint(-5, 5)
        for _ in range(abs(moves)):
            tetro.move_horizontal(1 if moves > 0 else -1)

        # 3. Hard drop with 80% chance
        if random.random() < 0.8:
            self.game.perform_hard_drop()

        self.last_action_time = current_time
