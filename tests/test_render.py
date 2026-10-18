"""Tests for scalar coloring and Pygame mesh rendering."""

import numpy as np

from bmi_debugger.render import NO_DATA_COLOR, PygameRenderer, scalar_color


def test_scalar_color_maps_range_and_marks_missing_values():
    low = scalar_color(0.0, 0.0, 10.0)
    high = scalar_color(10.0, 0.0, 10.0)

    assert low != high
    assert scalar_color(float("nan"), 0.0, 10.0) == NO_DATA_COLOR
    assert scalar_color(3.0, 3.0, 3.0) == scalar_color(3.0, 3.0, 3.0)


def test_renderer_draws_mesh_and_optional_velocity_arrows(
    pygame_module, mesh_and_snapshot
):
    mesh, snapshot = mesh_and_snapshot
    surface = pygame_module.Surface((1200, 800))
    renderer = PygameRenderer(pygame_module)

    renderer.draw(surface, mesh, snapshot, "water_level", False)
    first_cell_color = scalar_color(1.0, 1.0, 2.0)
    assert surface.get_at((250, 300))[:3] == first_cell_color

    renderer.draw(surface, mesh, snapshot, "velocity_magnitude", True)
    assert np.any(np.asarray(pygame_module.surfarray.array3d(surface)) != 0)
