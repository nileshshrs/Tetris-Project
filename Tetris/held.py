# held.py
from settings import *
from os import path
from pygame.image import load

class Held:
    def __init__(self):
        self.held_shape = None  # Initialize held shape to None
        self.display_surface = pygame.display.get_surface()

        # Calculate the height for the Held surface
        held_height = GAME_HEIGHT * PREVIEW_HEIGHT_FRACTION-PADDING  # Set height relative to preview fraction
        self.surface = pygame.Surface((SIDEBAR_WIDTH, held_height))  # Define the surface size
        self.rect = self.surface.get_rect(topleft=(PADDING, PADDING))  # Place at the top-left corner of the screen

        # Load shape images
        BASE_DIR = path.dirname(path.abspath(__file__))
        self.shape_surfaces = {
            shape: load(path.join(BASE_DIR, "assets", "graphics", f'{shape}.png')).convert_alpha()
            for shape in TETROMINOS.keys()
        }

        # Positioning settings for the held shape
        self.top_padding = 20  # Extra space at the top
        self.increment_height = self.surface.get_height() - self.top_padding  # Only 1 piece in this case

    def display_held(self):
        """Displays the held piece."""
        if self.held_shape is not None:  # Only display if there's a held shape
            shape_surface = self.shape_surfaces[self.held_shape]
            shape_rect = shape_surface.get_rect()

            # Center the shape horizontally in the surface
            x = (self.surface.get_width() - shape_rect.width) // 2
            # Position the shape at the top of the surface, with no vertical offset other than the top padding
            y = self.top_padding  # Position at the top of the surface

            # Update the rect position
            shape_rect.topleft = (x, y)
            self.surface.blit(shape_surface, shape_rect)  # Blit the shape onto the surface

    def run(self):
        """Run the held shape display process."""
        self.surface.fill(GRAY)  # Fill the surface with the gray background
        self.display_held()  # Call the function to display the held shape
        self.display_surface.blit(self.surface, self.rect)  # Blit the surface onto the main screen
        
        # Optional: Add border around the surface to visualize the position (for debugging)
        # pygame.draw.rect(self.display_surface, LINE_COLOR, self.rect, 2)  # Border around the surface
