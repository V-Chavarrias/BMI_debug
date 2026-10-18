"""Shared fixtures for debugger tests."""

import os

import numpy as np
import pytest

from bmi_debugger.model import Mesh, ModelSnapshot


class FakeBMIModel:
    def __init__(self) -> None:
        self.initialized = False
        self.finalized = False
        self.update_count = 0
        self.model_input: str | None = None
        self.model_time = 0.0
        self.variables: dict[str, np.ndarray | int | float] = {
            "ndx": 2,
            "ndx2d": 2,
            "xk": np.asarray([0.0, 1.0, 1.0, 0.0, 2.0, 2.0]),
            "yk": np.asarray([0.0, 0.0, 1.0, 1.0, 0.0, 1.0]),
            "flowelemnode": np.asarray(
                [[1, 2, 3, 4, -1], [2, 5, 6, 3, -1]], dtype=np.int32
            ),
            "s1": np.asarray([1.0, 2.0]),
            "ucmag": np.asarray([5.0, 2.0]),
            "ucx": np.asarray([3.0, 0.0]),
            "ucy": np.asarray([4.0, 2.0]),
            "hs": np.asarray([0.5, 1.5]),
        }

    def initialize(self, config_file: str) -> None:
        self.initialized = True
        self.model_input = config_file

    def update(self) -> None:
        self.update_count += 1
        self.model_time += 2.5

    def get_current_time(self) -> float:
        return self.model_time

    def get_var(self, name: str) -> np.ndarray | int | float:
        return self.variables[name]

    def finalize(self) -> None:
        self.finalized = True


@pytest.fixture
def model_paths(tmp_path):
    model_directory = tmp_path / "case"
    library_directory = tmp_path / "install" / "lib"
    model_directory.mkdir()
    library_directory.mkdir(parents=True)
    model_input = model_directory / "FlowFM.mdu"
    library_path = library_directory / "libdflowfm.so"
    model_input.write_text("[model]\n", encoding="utf-8")
    library_path.write_bytes(b"test library placeholder")
    return model_input, library_path


@pytest.fixture
def fake_bmi_factory():
    created_models: list[FakeBMIModel] = []

    def factory(library_path: str) -> FakeBMIModel:
        model = FakeBMIModel()
        model.library_path = library_path
        created_models.append(model)
        return model

    return factory, created_models


@pytest.fixture
def mesh_and_snapshot():
    mesh = Mesh(
        node_x=np.asarray([0.0, 1.0, 1.0, 0.0, 2.0, 2.0]),
        node_y=np.asarray([0.0, 0.0, 1.0, 1.0, 0.0, 1.0]),
        cells=(
            np.asarray([0, 1, 2, 3]),
            np.asarray([1, 4, 5, 2]),
        ),
    )
    snapshot = ModelSnapshot(
        step=1,
        model_time=2.5,
        water_level=np.asarray([1.0, 2.0]),
        velocity_magnitude=np.asarray([5.0, 2.0]),
        velocity_x=np.asarray([3.0, 0.0]),
        velocity_y=np.asarray([4.0, 2.0]),
        water_depth=np.asarray([0.5, 1.5]),
    )
    return mesh, snapshot


@pytest.fixture
def pygame_module(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    import pygame

    pygame.init()
    yield pygame
    pygame.quit()
