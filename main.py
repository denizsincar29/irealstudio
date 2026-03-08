import pygame
from pygame import midi, mixer
from accessible_output3.outputs.auto import Auto
from chords import ChordProgression, TimeSignature, Chord, Position


pygame.init()
midi.init()
mixer.init()
o = Auto()

progression = ChordProgression("My Progression", TimeSignature(4, 4), "C", "Jazz", [])
position = Position(1, 1)

# Set up the display
width, height = 800, 600
screen = pygame.display.set_mode((width, height))
pygame.display.set_caption("IReal Studio")

# Game loop
running = True
clock = pygame.time.Clock()

while running:
    clock.tick(60)
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                print("Up arrow pressed")
            elif event.key == pygame.K_DOWN:
                print("Down arrow pressed")
            elif event.key == pygame.K_LEFT:
                position = position - 1  # Move left by one beat
                o.output(f"{progression.find_chords_at_position(position)} at position {position}")
            elif event.key == pygame.K_RIGHT:
                position = position + 1  # Move right by one beat
                o.output(f"{progression.find_chords_at_position(position)} at position {position}")
    
    screen.fill((255, 255, 255))
    pygame.display.flip()

pygame.quit()