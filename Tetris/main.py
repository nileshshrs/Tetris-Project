from settings import *
from sys import exit

#components
from game import Game
from score import Score
from preview import Preview

class Main :
    def __init__(self) :

        #general
        pygame.init()
         
        self.display_surface = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock=pygame.time.Clock()
        pygame.display.set_caption("TETRIS")

        #components
        self.bag = create_weighted_bag()
        self.next_shapes = [get_next_tetromino(self.bag) for _ in range(3)]

        self.game = Game(self.get_next_shape)
        self.score=Score()
        self.preview = Preview()

  
        # print(self.next_shapes)
        # print("next shape", self.get_next_shape())

    def get_next_shape(self):
        next_shape = self.next_shapes.pop(0)
        self.new_shape= next_shape  # Get the next shape

        # print("firlst shape is f{next_shape}")
        self.next_shapes.append(get_next_tetromino(self.bag))  # Add a new shape from the bag to the end
        return next_shape
    
    
    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()
            #display
            self.display_surface.fill(GRAY)

            #components
            self.game.run()
            self.score.run()
            self.preview.run(self.next_shapes)

            #update the game
            pygame.display.update()
            self.clock.tick()



if __name__ == "__main__":
    main = Main()
    main.run()