from settings import *

class Score:
    def __init__(self):
        self.display_surface = pygame.display.get_surface()
        preview_height = GAME_HEIGHT * PREVIEW_HEIGHT_FRACTION
        score_height = GAME_HEIGHT - preview_height
        self.surface = pygame.Surface((SIDEBAR_WIDTH, score_height))
        self.rect = self.surface.get_rect(topright=(WINDOW_WIDTH - PADDING, preview_height + PADDING))
    
    def run(self):
        self.display_surface.blit(self.surface, self.rect)
