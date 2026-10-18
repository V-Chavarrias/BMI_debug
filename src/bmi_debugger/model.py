"""BMI model lifecycle and 2D D-Flow FM data extraction."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
import math
import os
from pathlib import Path
from typing import Protocol

import numpy as np


class ModelDataError(RuntimeError):
    """Raised when the BMI model exposes data that cannot be displayed safely."""


class BMIModel(Protocol):
    def initialize(self, config_file: str) -> object: ...

    def update(self) -> object: ...

    def get_current_time(self) -> object: ...

    def get_var(self, name: str) -> object: ...

    def finalize(self) -> object: ...


ModelFactory = Callable[[str], BMIModel]


@dataclass(frozen=True)
class Mesh:
    """2D flow-cell polygons represented by their node coordinates."""

    node_x: np.ndarray
    node_y: np.ndarray
    cells: tuple[np.ndarray, ...]

    @property
    def cell_centers(self) -> np.ndarray:
        """Return arithmetic cell-center coordinates for vector rendering."""
        return np.asarray(
            [
                (
                    np.mean(self.node_x[cell]),
                    np.mean(self.node_y[cell]),
                )
                for cell in self.cells
            ],
            dtype=np.float64,
        )


@dataclass(frozen=True)
class ModelSnapshot:
    """Field values copied from one completed model time step."""

    step: int
    model_time: float
    water_level: np.ndarray
    velocity_magnitude: np.ndarray
    velocity_x: np.ndarray
    velocity_y: np.ndarray
    water_depth: np.ndarray


class DFlowFMSession:
    """Own a BMI model from initialization through finalization."""

    def __init__(
        self,
        model_input: str | Path,
        library_path: str | Path,
        model_factory: ModelFactory | None = None,
    ) -> None:
        self.model_input = Path(model_input).expanduser().resolve()
        self.library_path = Path(library_path).expanduser().resolve()
        if self.model_input.suffix.lower() != ".mdu":
            raise ValueError(f"Expected a D-Flow FM .mdu input file: {self.model_input}")
        if not self.model_input.is_file():
            raise FileNotFoundError(f"D-Flow FM model input was not found: {self.model_input}")
        if not self.library_path.is_file():
            raise FileNotFoundError(
                f"D-Flow FM BMI library was not found: {self.library_path}"
            )

        self._model_factory = model_factory
        self._context: AbstractContextManager[DFlowFMSession] | None = None
        self._model: BMIModel | None = None
        self._initialized = False
        self._mesh: Mesh | None = None
        self._cell_count = 0
        self._flow_cell_count = 0
        self._step = 0

    def __enter__(self) -> DFlowFMSession:
        if self._context is not None:
            raise RuntimeError("This BMI session is already open.")
        self._context = self._open()
        return self._context.__enter__()

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
        if self._context is None:
            return False
        context = self._context
        self._context = None
        return context.__exit__(exc_type, exc_value, traceback)

    @contextmanager
    def _open(self) -> Iterator[DFlowFMSession]:
        previous_directory = Path.cwd()
        previous_library_path = os.environ.get("LD_LIBRARY_PATH")
        model: BMIModel | None = None
        initialized = False

        try:
            os.chdir(self.model_input.parent)
            self._add_library_directory()
            factory = self._model_factory or _create_bmi_model
            model = factory(str(self.library_path))
            self._model = model
            model.initialize(str(self.model_input))
            initialized = True
            self._initialized = True
            self._mesh = self._read_mesh()
            yield self
        finally:
            try:
                if initialized and model is not None:
                    model.finalize()
            finally:
                try:
                    os.chdir(previous_directory)
                finally:
                    if previous_library_path is None:
                        os.environ.pop("LD_LIBRARY_PATH", None)
                    else:
                        os.environ["LD_LIBRARY_PATH"] = previous_library_path
                    self._model = None
                    self._initialized = False
                    self._mesh = None

    def advance(self) -> ModelSnapshot:
        """Advance once and copy the latest 2D fields out of BMI."""
        model = self._require_model()
        model.update()
        self._step += 1

        water_level = self._read_field("s1")
        velocity_magnitude = self._read_field("ucmag")
        velocity_x = self._read_field("ucx")
        velocity_y = self._read_field("ucy")
        water_depth = self._read_field("hs")
        model_time = self._read_time()

        return ModelSnapshot(
            step=self._step,
            model_time=model_time,
            water_level=water_level,
            velocity_magnitude=velocity_magnitude,
            velocity_x=velocity_x,
            velocity_y=velocity_y,
            water_depth=water_depth,
        )

    @property
    def mesh(self) -> Mesh:
        """The initialized 2D mesh."""
        if self._mesh is None:
            raise RuntimeError("The BMI session must be initialized before reading its mesh.")
        return self._mesh

    @property
    def step(self) -> int:
        """Number of successful BMI update calls made by this session."""
        return self._step

    def _require_model(self) -> BMIModel:
        if not self._initialized or self._model is None:
            raise RuntimeError("The BMI session must be initialized before stepping.")
        return self._model

    def _add_library_directory(self) -> None:
        library_directory = str(self.library_path.parent)
        current_directories = [
            item
            for item in os.environ.get("LD_LIBRARY_PATH", "").split(os.pathsep)
            if item
        ]
        if library_directory not in current_directories:
            os.environ["LD_LIBRARY_PATH"] = os.pathsep.join(
                [library_directory, *current_directories]
            )

    def _read_mesh(self) -> Mesh:
        model = self._require_model()
        self._flow_cell_count = self._read_integer_scalar("ndx")
        self._cell_count = self._read_integer_scalar("ndx2d")
        if self._cell_count <= 0:
            raise ModelDataError(
                "The model has no 2D flow cells; 1D-only models are not supported."
            )
        if self._flow_cell_count < self._cell_count:
            raise ModelDataError(
                f"Invalid BMI cell counts: ndx={self._flow_cell_count}, "
                f"ndx2d={self._cell_count}."
            )

        node_x = self._read_coordinate("xk")
        node_y = self._read_coordinate("yk")
        if node_x.shape != node_y.shape:
            raise ModelDataError(
                f"BMI node coordinate sizes differ: xk={node_x.size}, yk={node_y.size}."
            )

        raw_connectivity = np.asarray(model.get_var("flowelemnode"))
        if raw_connectivity.ndim != 2:
            raise ModelDataError(
                "BMI variable 'flowelemnode' must be a two-dimensional cell-node array; "
                f"received shape {raw_connectivity.shape}."
            )
        if not np.issubdtype(raw_connectivity.dtype, np.integer):
            if (
                not np.issubdtype(raw_connectivity.dtype, np.floating)
                or not np.all(np.isfinite(raw_connectivity))
                or not np.all(raw_connectivity == np.rint(raw_connectivity))
            ):
                raise ModelDataError("BMI variable 'flowelemnode' must contain integer node IDs.")
            raw_connectivity = raw_connectivity.astype(np.int64)

        connectivity = self._orient_connectivity(raw_connectivity)
        cells: list[np.ndarray] = []
        for cell_index, row in enumerate(connectivity):
            node_ids = row[row > 0].astype(np.int64) - 1
            if node_ids.size > 2 and node_ids[0] == node_ids[-1]:
                node_ids = node_ids[:-1]
            if node_ids.size < 3:
                raise ModelDataError(
                    f"2D flow cell {cell_index} has fewer than three mesh nodes."
                )
            if np.any(node_ids >= node_x.size):
                raise ModelDataError(
                    f"2D flow cell {cell_index} references a node outside the xk/yk arrays."
                )
            if not np.all(np.isfinite(node_x[node_ids])) or not np.all(
                np.isfinite(node_y[node_ids])
            ):
                raise ModelDataError(
                    f"2D flow cell {cell_index} references a non-finite mesh coordinate."
                )
            cells.append(node_ids)

        return Mesh(node_x=node_x, node_y=node_y, cells=tuple(cells))

    def _orient_connectivity(self, connectivity: np.ndarray) -> np.ndarray:
        rows, columns = connectivity.shape
        if rows == self._cell_count:
            return connectivity
        if columns == self._cell_count:
            return connectivity.T
        if rows > self._cell_count and columns < rows:
            return connectivity[: self._cell_count]
        if columns > self._cell_count and rows < columns:
            return connectivity.T[: self._cell_count]
        raise ModelDataError(
            "Could not match BMI variable 'flowelemnode' to ndx2d="
            f"{self._cell_count}; received shape {connectivity.shape}."
        )

    def _read_coordinate(self, name: str) -> np.ndarray:
        model = self._require_model()
        values = np.asarray(model.get_var(name))
        if values.ndim != 1 or values.size == 0:
            raise ModelDataError(
                f"BMI node coordinate '{name}' must be a non-empty one-dimensional array; "
                f"received shape {values.shape}."
            )
        if not np.issubdtype(values.dtype, np.number) or np.iscomplexobj(values):
            raise ModelDataError(f"BMI node coordinate '{name}' must contain real numbers.")
        coordinates = np.array(values, dtype=np.float64, copy=True)
        if not np.all(np.isfinite(coordinates)):
            raise ModelDataError(f"BMI node coordinate '{name}' contains non-finite values.")
        return coordinates

    def _read_integer_scalar(self, name: str) -> int:
        model = self._require_model()
        value = np.asarray(model.get_var(name))
        if value.size != 1 or not np.issubdtype(value.dtype, np.number):
            raise ModelDataError(
                f"BMI value '{name}' must be a numeric scalar; received shape {value.shape}."
            )
        numeric_value = float(value.item())
        if not math.isfinite(numeric_value) or not numeric_value.is_integer():
            raise ModelDataError(f"BMI value '{name}' must be a finite integer.")
        return int(numeric_value)

    def _read_field(self, name: str) -> np.ndarray:
        model = self._require_model()
        values = np.asarray(model.get_var(name))
        if values.ndim != 1:
            raise ModelDataError(
                f"BMI field '{name}' must be one-dimensional for 2D display; "
                f"received shape {values.shape}."
            )
        if not np.issubdtype(values.dtype, np.number) or np.iscomplexobj(values):
            raise ModelDataError(f"BMI field '{name}' must contain real numbers.")
        if values.size not in (self._cell_count, self._flow_cell_count):
            raise ModelDataError(
                f"BMI field '{name}' has {values.size} values; expected "
                f"ndx2d={self._cell_count} or ndx={self._flow_cell_count}. "
                "3D or otherwise incompatible fields are not supported."
            )
        return np.array(values[: self._cell_count], dtype=np.float64, copy=True)

    def _read_time(self) -> float:
        model = self._require_model()
        time_value = np.asarray(model.get_current_time())
        if time_value.size != 1:
            raise ModelDataError(
                f"BMI current time must be a scalar; received shape {time_value.shape}."
            )
        value = float(time_value.item())
        if not math.isfinite(value):
            raise ModelDataError("BMI current time is not finite.")
        return value


def _create_bmi_model(library_path: str) -> BMIModel:
    try:
        from bmi.wrapper import BMIWrapper
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "Could not import bmi-python. Install the project runtime dependencies "
            "with `python -m pip install -e .`."
        ) from error
    return BMIWrapper(library_path)
