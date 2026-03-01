from settings import *
from os import path
import time

class Score:
    def __init__(self):
        self.display_surface = pygame.display.get_surface()
        preview_height = GAME_HEIGHT * PREVIEW_HEIGHT_FRACTION
        score_height = GAME_HEIGHT - preview_height
        self.surface = pygame.Surface((SIDEBAR_WIDTH, score_height))
        self.rect = self.surface.get_rect(topright=(WINDOW_WIDTH - PADDING, preview_height + PADDING))

        # Font
        BASE_DIR = path.dirname(path.abspath(__file__))
        self.font = pygame.font.Font(path.join(BASE_DIR, "assets", "graphics", "Russo_One.ttf"), 20)

        # Positioning
        self.top_padding = 20
        self.increment_height = (self.surface.get_height() - self.top_padding) // 2  # For score and time

        # Data
        self.score = 0
        # The next two lines are for standalone only, comment or remove in tray mode:

        self.levels = 1

        # The next two lines are for standalone only, comment or remove in tray mode:

        self.start_time = time.time()
        self.frozen_time = None  # Stores time at game over

    def format_time(self, seconds):
        """Converts seconds to hh:mm:ss format."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def display_text(self, pos, text):
        text_surface = self.font.render(text, True, LINE_COLOR)
        text_rect = text_surface.get_rect(center=pos)
        self.surface.blit(text_surface, text_rect)

    def run(self):
        self.surface.fill(GRAY)

        # Freeze time if game is over
        if self.frozen_time is not None:
            elapsed_seconds = self.frozen_time
        else:
            elapsed_seconds = int(time.time() - self.start_time)

        formatted_time = self.format_time(elapsed_seconds)

        # Draw score and time
        for i, (label, value) in enumerate([('Score', self.score), ('Time', formatted_time)]):
            x = self.surface.get_width() // 2
            y_label = self.top_padding + (i * self.increment_height)
            y_value = y_label + 35
            self.display_text((x, y_label), label)
            self.display_text((x, y_value), str(value))

        self.display_surface.blit(self.surface, self.rect)
