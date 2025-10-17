import pygame
import sys

window = pygame.display.set_mode((800, 500), pygame.NOFRAME)
pygame.display.set_caption("mayaSetup")

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

    pygame.draw.circle(
        window,
        (255, 0, 0),
        (780, 20),
        7
    )
    pygame.display.flip()