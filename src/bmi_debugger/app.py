"""Pygame event loop for the interactive BMI debugger."""

from __future__ import annotations

from typing import Any

from .model import DFlowFMSession, ModelSnapshot
from .render import PygameRenderer


class DebuggerApp:
    """Handle keyboard controls and render the current model state."""

    def __init__(
        self,
        model: DFlowFMSession,
        pygame_module: Any | None = None,
        window_size: tuple[int, int] = (1200, 800),
    ) -> None:
        self.model = model
        self._pygame_module = pygame_module
        self.window_size = window_size
        self.snapshot: ModelSnapshot | None = None
        self.selected_field = "water_level"
        self.show_velocity_arrows = False
        self.running = True

    def handle_key(self, key: int) -> None:
        """Apply one key press; a Space key advances the model exactly once."""
        pygame = self._pygame()
        if key == pygame.K_SPACE:
            self.snapshot = self.model.advance()
        elif key in (pygame.K_1, pygame.K_KP1):
            self.selected_field = "water_level"
        elif key in (pygame.K_2, pygame.K_KP2):
            self.selected_field = "velocity_magnitude"
        elif key in (pygame.K_3, pygame.K_KP3):
            self.selected_field = "water_depth"
        elif key == pygame.K_a and self.selected_field == "velocity_magnitude":
            self.show_velocity_arrows = not self.show_velocity_arrows
        elif key in (pygame.K_ESCAPE, pygame.K_q):
            self.running = False

    def run(self) -> None:
        """Open the Pygame window and process input until the user exits."""
        pygame = self._pygame()
        pygame.init()
        try:
            screen = pygame.display.set_mode(self.window_size)
            pygame.display.set_caption("D-Flow FM BMI Debugger")
            renderer = PygameRenderer(pygame)
            clock = pygame.time.Clock()
            self.running = True

            while self.running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.KEYDOWN:
                        self.handle_key(event.key)

                if self.running:
                    renderer.draw(
                        screen,
                        self.model.mesh,
                        self.snapshot,
                        self.selected_field,
                        self.show_velocity_arrows,
                    )
                    pygame.display.flip()
                clock.tick(30)
        finally:
            pygame.quit()

    def _pygame(self) -> Any:
        if self._pygame_module is None:
            import pygame

            self._pygame_module = pygame
        return self._pygame_module
