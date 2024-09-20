from settings import *

class Preview:
    def __init__(self, next_shapes):
        self.display_surface = pygame.display.get_surface()
        self.surface = pygame.Surface((SIDEBAR_WIDTH, GAME_HEIGHT * PREVIEW_HEIGHT_FRACTION - PADDING))
        self.rect = self.surface.get_rect(topright=(WINDOW_WIDTH - PADDING, PADDING))

        #shapes
        self.next_shapes = next_shapes
        self.shape_surfaces = {''}
    
    def run(self):
        self.display_surface.blit(self.surface, self.rect)