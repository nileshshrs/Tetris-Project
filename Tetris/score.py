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

        # Increase spacing to push everything down a bit
        self.top_padding = 20  
        self.increment_height = (self.surface.get_height() - self.top_padding) // 2  # Adjusted for 2 items

        # Data
        self.score = 0
        self.start_time = time.time()  # Track game start time

    def format_time(self, seconds):
        """Converts seconds to hh:mm:ss format."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{hours:02}:{minutes:02}:{seconds:02}"  # Ensure two-digit formatting

    def display_text(self, pos, text):
        text_surface = self.font.render(text, True, LINE_COLOR)
        text_rect = text_surface.get_rect(center=pos)
        self.surface.blit(text_surface, text_rect)

    def run(self):
        self.surface.fill(GRAY)  # Fill the surface with a background color
        
        # Calculate elapsed time and format it
        elapsed_seconds = int(time.time() - self.start_time)  # Convert to seconds
        formatted_time = self.format_time(elapsed_seconds)

        # Display Score and Time
        for i, (label, value) in enumerate([('Score', self.score), ('Time', formatted_time)]):
            x = self.surface.get_width() // 2
            y_label = self.top_padding + (i * self.increment_height)  # More padding
            y_value = y_label + 35  # Keep values separate from labels

            self.display_text((x, y_label), label)  # Draw label
            self.display_text((x, y_value), str(value))  # Draw value below label

        # Draw the score display on the main screen
        pygame.draw.rect(self.surface, LINE_COLOR, self.rect, 2) 
        self.display_surface.blit(self.surface, self.rect)
        # pygame.draw.rect(self.display_surface, LINE_COLOR, self.rect, 2, 2)  # Draw a border

