from settings import *
import time
import pygame
import random
import os
import sys

import multiprocessing

# Components
from game import Game
from score import Score
from lines import Lines
from preview import Preview
from held import Held

class Main:
    def __init__(self, seed=None, use_async_ai=True, ai_class=None, ai_kwargs=None):
        # ===== Random Seed Debugging =====
        if seed is None:
            # Generate a unique seed using time, PID, and randomness
            seed = time.time_ns() ^ os.getpid() ^ random.randint(0, 1_000_000)
        random.seed(seed)
        rand_check = random.random()
        print(f"[PID {os.getpid()}] Using seed: {seed} | Random check: {rand_check}")
        # ==================================

        # ==== UNCOMMENT FOR NORMAL/STANDALONE MODE ====
        pygame.init()
        
        # --- AUDIO INITIALIZATION ---
        if os.environ.get("SDL_VIDEODRIVER") != "dummy":
            try:
                pygame.mixer.init()
                # Try multiple extensions in case user downloads wav, mp3, or ogg
                bgm_base = os.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'graphics', 'audio', 'yours_forever'))
                bgm_path = None
                for ext in ['.mp3', '.ogg', '.wav', '.flac']:
                    if os.path.exists(bgm_base + ext):
                        bgm_path = bgm_base + ext
                        break

                if bgm_path:
                    pygame.mixer.music.load(bgm_path)
                    pygame.mixer.music.set_volume(0.5) # Adjust volume (0.0 to 1.0)
                    pygame.mixer.music.play(-1) # Play in an infinite loop
                else:
                    print(f"[Audio] BGM file not found. To enable music, place 'yours_forever.mp3' (or .ogg/.wav) at:")
                    print(f"[Audio] {bgm_base}.[ext]")
            except Exception as e:
                print(f"[Audio] Warning: Could not initialize or play BGM - {e}")
        # ----------------------------

        self.display_surface = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        pygame.display.set_caption("TETRIS")
        # ===============================================

        # Piece bag and preview queue
        self.bag = create_7bag()
        print(f"[PID {os.getpid()}] Initial bag: {self.bag}")  # Debug: log bag order
        self.next_shapes = [get_next_tetromino(self.bag) for _ in range(3)]

        # Pop the first shape for the initial tetromino (can't use get_next_shape
        # yet because self.game doesn't exist until Game.__init__ returns)
        initial_shape = self.next_shapes.pop(0)
        self.next_shapes.append(get_next_tetromino(self.bag))

        # ---- Phase 6: Async AI Worker ----
        self._ai_process = None
        self._parent_conn = None

        if use_async_ai:
            self._parent_conn, child_conn = multiprocessing.Pipe()
            
            # Import worker function
            sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
            from AI.worker import run_ai
            
            ai_kwargs = ai_kwargs or {}
            worker_weights = ai_kwargs.get('weights', None)
            
            self._ai_process = multiprocessing.Process(
                target=run_ai,
                args=(child_conn, worker_weights),
                daemon=True
            )
            self._ai_process.start()
            
            # Pass pipe to AI through ai_kwargs
            ai_kwargs['async_pipe'] = self._parent_conn

        # Game and UI components
        self.game = Game(
            self.get_next_shape, self.update_score, self.get_held_shape,
            initial_shape, ai_class=ai_class, ai_kwargs=ai_kwargs
        )
        self.score = Score()
        self.lines = Lines()
        self.held = Held()
        self.preview = Preview()
        self.game.current_next_shape = self.next_shapes[0]

    def update_score(self, lines, score, levels):
        self.score.score = score
        self.score.levels = levels
        self.lines.lines = lines
        self.lines.levels = levels

    def get_next_shape(self):
        next_piece = self.next_shapes.pop(0)
        self.next_shapes.append(get_next_tetromino(self.bag))
        self.game.is_held = False
        self.game.current_next_shape = self.next_shapes[0]
        return next_piece

    def get_held_shape(self, shape):
        self.held.held_shape = shape

    def run(self):
        try:
            # ==== UNCOMMENT FOR NORMAL/STANDALONE MODE ====
            while True:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        exit()

                self.display_surface.fill(GRAY)

                if self.game.is_game_over:
                    # Stop music on game over
                    if os.environ.get("SDL_VIDEODRIVER") != "dummy" and pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                        pygame.mixer.music.stop()

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

                    # --- FPS Display ---
                    fps_text = pygame.font.SysFont("arial", 16, bold=True).render(f"FPS: {int(self.clock.get_fps())}", True, (0, 255, 0))
                    self.display_surface.blit(fps_text, (10, 10))

                    pygame.display.update()
                    self.clock.tick(60)
                    continue

                # --- Normal game loop ---
                self.game.run()
                self.score.run()
                self.lines.run()
                self.preview.run(self.next_shapes)
                self.held.run()

                # --- FPS Display ---
                fps_text = pygame.font.SysFont("arial", 16, bold=True).render(f"FPS: {int(self.clock.get_fps())}", True, (0, 255, 0))
                self.display_surface.blit(fps_text, (10, 10))

                pygame.display.update()
                self.clock.tick(60)
            # ==============================================
        finally:
            self._cleanup()

    def _cleanup(self):
        """Clean up worker process."""
        if self._parent_conn:
            try:
                self._parent_conn.send(None)  # shutdown signal
            except Exception:
                pass
        if self._ai_process and self._ai_process.is_alive():
            self._ai_process.terminate()
            self._ai_process.join(timeout=2)

        # --- Tray mode: just draw a single frame for use in multi-board tray ---
        # self.game.surface.fill(GRAY)
        # self.game.run()
        # self.score.run()
        # self.lines.run()
        # self.preview.run(self.next_shapes)
        # self.held.run()
        # No pygame.display.update()

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main = Main()
    # ==== UNCOMMENT FOR NORMAL/STANDALONE MODE ====
    main.run()
    # ==============================================