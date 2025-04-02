from settings import *
from os import path
from pygame.image import load

class Preview:
    def __init__(self):
        self.display_surface = pygame.display.get_surface()
        self.surface = pygame.Surface((SIDEBAR_WIDTH, GAME_HEIGHT * PREVIEW_HEIGHT_FRACTION - PADDING))
        self.rect = self.surface.get_rect(topright=(WINDOW_WIDTH - PADDING, PADDING))

        # Load shape images
        BASE_DIR = path.dirname(path.abspath(__file__))
        self.shape_surfaces = {
            shape: load(path.join(BASE_DIR, "assets", "graphics", f'{shape}.png')).convert_alpha()
            for shape in TETROMINOS.keys()
        }

        # Positioning settings
        self.increment_height = self.surface.get_height() // 3

    def display_pieces(self, shapes):
        for i, shape in enumerate(shapes):
            shape_surface = self.shape_surfaces[shape]
            shape_rect = shape_surface.get_rect()  

            # Center horizontally
            x = (self.surface.get_width() - shape_rect.width) // 2  
            # Adjust vertical positioning
            y = (self.increment_height - shape_rect.height) // 2 + i * self.increment_height  

            # Update the rect position
            shape_rect.topleft = (x, y)
            self.surface.blit(shape_surface, shape_rect)  # Blit the shape at its centered position

    def run(self, next_shapes):
        self.surface.fill(GRAY)  # Fill the surface with a background color
        self.display_pieces(next_shapes)
        self.display_surface.blit(self.surface, self.rect)  # Blit the surface to the display surface
        pygame.draw.rect(self.display_surface, LINE_COLOR, self.rect, 2, 2)  # Draw a border
