"""Pygame rendering for mesh fields, controls, and optional velocity arrows."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .model import Mesh, ModelSnapshot


BLACK = (0, 0, 0)
TEXT_COLOR = (230, 230, 230)
GRID_COLOR = (92, 92, 92)
NO_DATA_COLOR = (60, 60, 60)
ARROW_COLOR = (255, 255, 255)
FIELD_INFO = {
    "water_level": ("Water level (s1)", "m"),
    "velocity_magnitude": ("Velocity magnitude (ucmag)", "m/s"),
    "water_depth": ("Water depth (hs)", "m"),
}
MAX_VELOCITY_ARROWS = 800


def scalar_color(value: float, minimum: float, maximum: float) -> tuple[int, int, int]:
    """Map a scalar to a blue-green-yellow ramp, using gray for missing values."""
    if not math.isfinite(value):
        return NO_DATA_COLOR
    fraction = 0.5 if maximum <= minimum else (value - minimum) / (maximum - minimum)
    fraction = min(1.0, max(0.0, fraction))
    low = (25, 65, 210)
    middle = (25, 205, 170)
    high = (255, 220, 45)
    if fraction <= 0.5:
        ratio = fraction * 2.0
        first, second = low, middle
    else:
        ratio = (fraction - 0.5) * 2.0
        first, second = middle, high
    return tuple(
        round(start + ratio * (end - start)) for start, end in zip(first, second)
    )


class PygameRenderer:
    """Draw one mesh and its selected field into a Pygame surface."""

    def __init__(self, pygame_module: Any) -> None:
        self.pygame = pygame_module
        if not self.pygame.font.get_init():
            self.pygame.font.init()
        self.font = self._load_font(18)
        self.heading_font = self._load_font(24)

    def draw(
        self,
        surface: Any,
        mesh: Mesh,
        snapshot: ModelSnapshot | None,
        selected_field: str,
        show_velocity_arrows: bool,
    ) -> None:
        if selected_field not in FIELD_INFO:
            raise ValueError(f"Unknown display field: {selected_field}")
        if snapshot is not None:
            values = np.asarray(getattr(snapshot, selected_field))
            if values.ndim != 1 or values.size != len(mesh.cells):
                raise ValueError(
                    f"Display field '{selected_field}' must contain one value per cell; "
                    f"received shape {values.shape} for {len(mesh.cells)} cells."
                )
            finite_values = values[np.isfinite(values)]
            minimum = float(np.min(finite_values)) if finite_values.size else math.nan
            maximum = float(np.max(finite_values)) if finite_values.size else math.nan
        else:
            values = None
            minimum = math.nan
            maximum = math.nan

        width, height = surface.get_size()
        surface.fill(BLACK)
        view_rect = self.pygame.Rect(20, 78, max(1, width - 300), max(1, height - 145))
        project = self._make_projector(mesh, view_rect)
        projected_nodes = [
            project(float(x), float(y)) for x, y in zip(mesh.node_x, mesh.node_y)
        ]
        projected_centers = [
            project(float(center[0]), float(center[1])) for center in mesh.cell_centers
        ]

        for cell_index, cell in enumerate(mesh.cells):
            polygon = [projected_nodes[int(node)] for node in cell]
            fill_color = (
                NO_DATA_COLOR
                if values is None
                else scalar_color(float(values[cell_index]), minimum, maximum)
            )
            self.pygame.draw.polygon(surface, fill_color, polygon)
            self.pygame.draw.polygon(surface, GRID_COLOR, polygon, 1)

        if (
            snapshot is not None
            and selected_field == "velocity_magnitude"
            and show_velocity_arrows
        ):
            self._draw_velocity_arrows(surface, mesh, snapshot, projected_centers)

        self._draw_header(surface, snapshot, selected_field, show_velocity_arrows)
        self._draw_legend(surface, selected_field, minimum, maximum, values is not None)
        self._draw_controls(surface, height)

    def _make_projector(self, mesh: Mesh, view_rect: Any) -> Any:
        padding = 12
        x_min = float(np.min(mesh.node_x))
        x_max = float(np.max(mesh.node_x))
        y_min = float(np.min(mesh.node_y))
        y_max = float(np.max(mesh.node_y))
        span_x = max(x_max - x_min, 1e-12)
        span_y = max(y_max - y_min, 1e-12)
        scale = min(
            max(1, view_rect.width - 2 * padding) / span_x,
            max(1, view_rect.height - 2 * padding) / span_y,
        )
        center_x = (x_min + x_max) * 0.5
        center_y = (y_min + y_max) * 0.5

        def project(x: float, y: float) -> tuple[int, int]:
            return (
                round(view_rect.centerx + (x - center_x) * scale),
                round(view_rect.centery - (y - center_y) * scale),
            )

        return project

    def _draw_velocity_arrows(
        self,
        surface: Any,
        mesh: Mesh,
        snapshot: ModelSnapshot,
        projected_centers: list[tuple[int, int]],
    ) -> None:
        speeds = np.asarray(snapshot.velocity_magnitude)
        max_speed = float(np.max(speeds[np.isfinite(speeds)])) if np.any(np.isfinite(speeds)) else 0.0
        if max_speed <= 0.0:
            return

        stride = max(1, math.ceil(len(mesh.cells) / MAX_VELOCITY_ARROWS))
        for index in range(0, len(mesh.cells), stride):
            u = float(snapshot.velocity_x[index])
            v = float(snapshot.velocity_y[index])
            speed = math.hypot(u, v)
            if not math.isfinite(speed) or speed <= 0.0:
                continue

            start_x, start_y = projected_centers[index]
            length = 5.0 + 22.0 * min(1.0, speed / max_speed)
            end_x = round(start_x + (u / speed) * length)
            end_y = round(start_y - (v / speed) * length)
            self.pygame.draw.line(
                surface, ARROW_COLOR, (start_x, start_y), (end_x, end_y), 2
            )

            angle = math.atan2(end_y - start_y, end_x - start_x)
            head_length = 6.0
            left = (
                round(end_x - head_length * math.cos(angle - math.pi / 6)),
                round(end_y - head_length * math.sin(angle - math.pi / 6)),
            )
            right = (
                round(end_x - head_length * math.cos(angle + math.pi / 6)),
                round(end_y - head_length * math.sin(angle + math.pi / 6)),
            )
            self.pygame.draw.polygon(surface, ARROW_COLOR, [(end_x, end_y), left, right])

    def _draw_header(
        self,
        surface: Any,
        snapshot: ModelSnapshot | None,
        selected_field: str,
        show_velocity_arrows: bool,
    ) -> None:
        width, _ = surface.get_size()
        label, units = FIELD_INFO[selected_field]
        self._draw_text(surface, "D-Flow FM BMI Debugger", (20, 16), self.heading_font)
        if snapshot is None:
            time_text = "Time: waiting for first step"
            step_text = "Step: 0"
        else:
            time_text = f"Time: {snapshot.model_time:g}"
            step_text = f"Step: {snapshot.step}"
        self._draw_text(surface, time_text, (width - 280, 18))
        self._draw_text(surface, step_text, (width - 280, 42))
        arrow_text = (
            f"Arrows: {'on' if show_velocity_arrows else 'off'}"
            if selected_field == "velocity_magnitude"
            else ""
        )
        self._draw_text(
            surface,
            f"{label} [{units}]  {arrow_text}",
            (20, 52),
        )

    def _draw_legend(
        self,
        surface: Any,
        selected_field: str,
        minimum: float,
        maximum: float,
        has_snapshot: bool,
    ) -> None:
        width, height = surface.get_size()
        panel_x = width - 260
        label, units = FIELD_INFO[selected_field]
        self._draw_text(surface, "Value scale", (panel_x, 112), self.heading_font)
        bar = self.pygame.Rect(panel_x, 156, 28, max(60, height - 290))
        segments = 96
        for index in range(segments):
            fraction = 1.0 - index / max(1, segments - 1)
            top = bar.y + round(index * bar.height / segments)
            bottom = bar.y + round((index + 1) * bar.height / segments)
            self.pygame.draw.rect(
                surface,
                scalar_color(fraction, 0.0, 1.0),
                self.pygame.Rect(bar.x, top, bar.width, max(1, bottom - top)),
            )
        self.pygame.draw.rect(surface, GRID_COLOR, bar, 1)
        if has_snapshot and math.isfinite(minimum) and math.isfinite(maximum):
            max_text = f"{maximum:.4g} {units}"
            min_text = f"{minimum:.4g} {units}"
        else:
            max_text = min_text = "no data"
        self._draw_text(surface, max_text, (panel_x + 38, bar.y))
        self._draw_text(surface, min_text, (panel_x + 38, bar.bottom - 20))
        self._draw_text(
            surface,
            "Gray cells have no finite value.",
            (panel_x, bar.bottom + 30),
        )
        self._draw_text(
            surface,
            "Press Space to run a step."
            if not has_snapshot
            else f"Field: {label}",
            (panel_x, bar.bottom + 58),
        )

    def _draw_controls(self, surface: Any, height: int) -> None:
        self._draw_text(
            surface,
            "SPACE step | 1 water level | 2 velocity | 3 depth | A arrows | ESC/Q quit",
            (20, height - 32),
        )

    def _draw_text(
        self,
        surface: Any,
        text: str,
        position: tuple[int, int],
        font: Any | None = None,
    ) -> None:
        if not text:
            return
        rendered = (font or self.font).render(text, True, TEXT_COLOR)
        surface.blit(rendered, position)

    def _load_font(self, size: int) -> Any:
        for family in (
            "Courier New",
            "CourierNew",
            "Liberation Mono",
            "DejaVu Sans Mono",
            "monospace",
        ):
            font_path = self.pygame.font.match_font(family)
            if font_path:
                return self.pygame.font.Font(font_path, size)
        return self.pygame.font.Font(None, size)
