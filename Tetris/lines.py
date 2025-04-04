from settings import *
from os import path
from pygame.image import load

class Lines:
    def __init__(self):
        self.display_surface = pygame.display.get_surface()
        preview_height = GAME_HEIGHT * PREVIEW_HEIGHT_FRACTION
        lines_height = GAME_HEIGHT - preview_height
        
        # Move to the left side
        self.surface = pygame.Surface((SIDEBAR_WIDTH, lines_height))
        self.rect = self.surface.get_rect(topleft=(PADDING, preview_height + PADDING))  # Moved to left

        # Font
        BASE_DIR = path.dirname(path.abspath(__file__))
        self.font = pygame.font.Font(path.join(BASE_DIR, "assets", "graphics", "Russo_One.ttf"), 20)

        # Increase spacing to push everything down a bit
        self.top_padding = 30  # Increased padding to give more space at the top
        self.increment_height = (self.surface.get_height() - self.top_padding) // 2  # Adjusted for 2 items

        # Data
        self.levels = 1
        self.lines = 0

    def display_text(self, pos, text):
        text_surface = self.font.render(text, True, LINE_COLOR)
        text_rect = text_surface.get_rect(center=pos)
        self.surface.blit(text_surface, text_rect)

    def run(self):
        self.surface.fill(GRAY) # Fill the surface with a background color
        # Display Level and Lines
        for i, (label, value) in enumerate([('Level', self.levels), ('Lines', self.lines)]):
            x = self.surface.get_width() // 2
            y_label = self.top_padding + (i * self.increment_height)  # More padding
            y_value = y_label + 35  # Keep values separate from labels

            self.display_text((x, y_label), label)  # Draw label
            self.display_text((x, y_value), str(value))  # Draw value below label

        # Draw the border around the Lines surface
        # pygame.draw.rect(self.surface, LINE_COLOR, self.rect, 2)  # Border for the Lines area

        # Draw the lines display on the main screen
        self.display_surface.blit(self.surface, self.rect)
