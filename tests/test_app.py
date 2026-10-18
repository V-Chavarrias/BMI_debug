"""Tests for debugger keyboard controls."""

from bmi_debugger.app import DebuggerApp


class FakeSession:
    def __init__(self, mesh, snapshot) -> None:
        self.mesh = mesh
        self.snapshot = snapshot
        self.advance_count = 0

    def advance(self):
        self.advance_count += 1
        return self.snapshot


def test_keys_select_fields_toggle_arrows_and_step(
    pygame_module, mesh_and_snapshot
):
    mesh, snapshot = mesh_and_snapshot
    model = FakeSession(mesh, snapshot)
    app = DebuggerApp(model, pygame_module=pygame_module)

    app.handle_key(pygame_module.K_2)
    assert app.selected_field == "velocity_magnitude"
    assert model.advance_count == 0

    app.handle_key(pygame_module.K_a)
    assert app.show_velocity_arrows

    app.handle_key(pygame_module.K_SPACE)
    assert model.advance_count == 1
    assert app.snapshot is snapshot

    app.handle_key(pygame_module.K_3)
    assert app.selected_field == "water_depth"
    assert model.advance_count == 1

    app.handle_key(pygame_module.K_a)
    assert app.show_velocity_arrows

    app.handle_key(pygame_module.K_ESCAPE)
    assert not app.running
