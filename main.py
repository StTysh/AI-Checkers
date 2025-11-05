from __future__ import annotations

import pygame

from core.game import Game
from ui.pygame_gui import CheckersGUI


def main() -> None:
	pygame.init()
	try:
		game = Game()
		gui = CheckersGUI(game)
		gui.run()
	finally:
		pygame.quit()


if __name__ == "__main__":
	main()
