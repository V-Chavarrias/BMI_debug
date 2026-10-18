"""Tests for BMI lifecycle and field extraction."""

import os
from pathlib import Path

import numpy as np
import pytest

from bmi_debugger.model import DFlowFMSession, ModelDataError


def test_session_loads_mesh_and_advances_one_step(
    model_paths, fake_bmi_factory, monkeypatch
):
    model_input, library_path = model_paths
    factory, created_models = fake_bmi_factory
    original_directory = Path.cwd()
    original_library_path = os.environ.get("LD_LIBRARY_PATH")
    monkeypatch.setenv("LD_LIBRARY_PATH", "/existing/native-libraries")

    with DFlowFMSession(model_input, library_path, factory) as session:
        model = created_models[0]
        assert Path.cwd() == model_input.parent
        assert model.initialized
        assert model.model_input == str(model_input)
        assert model.library_path == str(library_path)
        assert os.environ["LD_LIBRARY_PATH"].split(os.pathsep)[0] == str(
            library_path.parent
        )
        assert session.step == 0
        assert len(session.mesh.cells) == 2
        np.testing.assert_array_equal(session.mesh.cells[0], [0, 1, 2, 3])
        np.testing.assert_array_equal(session.mesh.cells[1], [1, 4, 5, 2])

        snapshot = session.advance()
        assert snapshot.step == 1
        assert snapshot.model_time == 2.5
        assert model.update_count == 1
        np.testing.assert_allclose(snapshot.water_level, [1.0, 2.0])
        np.testing.assert_allclose(snapshot.velocity_magnitude, [5.0, 2.0])
        np.testing.assert_allclose(snapshot.water_depth, [0.5, 1.5])

    assert created_models[0].finalized
    assert Path.cwd() == original_directory
    assert os.environ["LD_LIBRARY_PATH"] == "/existing/native-libraries"
    assert original_library_path != os.environ["LD_LIBRARY_PATH"]


def test_incompatible_velocity_shape_finalizes_and_restores_working_directory(
    model_paths, fake_bmi_factory
):
    model_input, library_path = model_paths
    factory, created_models = fake_bmi_factory
    original_directory = Path.cwd()

    def factory_with_3d_velocity(path: str):
        model = factory(path)
        model.variables["ucx"] = np.asarray([1.0, 2.0, 3.0, 4.0])
        return model

    with pytest.raises(ModelDataError, match="3D or otherwise incompatible"):
        with DFlowFMSession(model_input, library_path, factory_with_3d_velocity) as session:
            session.advance()

    assert created_models[0].update_count == 1
    assert created_models[0].finalized
    assert Path.cwd() == original_directory


def test_invalid_mesh_finalizes_model_during_initialization(
    model_paths, fake_bmi_factory
):
    model_input, library_path = model_paths
    factory, created_models = fake_bmi_factory

    def factory_with_invalid_mesh(path: str):
        model = factory(path)
        model.variables["flowelemnode"] = np.asarray([[1, 2, -1], [2, 0, 0]])
        return model

    with pytest.raises(ModelDataError, match="fewer than three"):
        with DFlowFMSession(model_input, library_path, factory_with_invalid_mesh):
            pass

    assert created_models[0].finalized


def test_model_and_library_paths_are_validated(model_paths):
    model_input, library_path = model_paths

    with pytest.raises(ValueError, match="\\.mdu"):
        DFlowFMSession(model_input.with_suffix(".xml"), library_path)
    with pytest.raises(FileNotFoundError, match="BMI library"):
        DFlowFMSession(model_input, library_path.with_name("missing.so"))
