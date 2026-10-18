# D-Flow FM BMI Debugger

An interactive debugger for stepping a 2D D-Flow FM model through its Basic
Model Interface (BMI). The debugger draws the unstructured grid, advances one
time step on demand, and colors cells with BMI data.

## Requirements

- Python 3.10 or newer
- `bmi-python`
- Pygame
- A BMI-enabled D-Flow FM shared library (`libdflowfm.so`) and its runtime
  dependencies
- A D-Flow FM model input file (`.mdu`) and the input files it references

## Install

Create an environment and install the project with its test dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Run

Pass the model input and the exact BMI shared-library path:

```bash
python main_BMI.py \
  --mdu /path/to/model/FlowFM.mdu \
  --library /path/to/delft3d/install/lib/libdflowfm.so
```

The installed console command is equivalent:

```bash
bmi-debugger --mdu /path/to/model/FlowFM.mdu \
  --library /path/to/delft3d/install/lib/libdflowfm.so
```

Files referenced by the `.mdu` are resolved from the model input's directory.
The debugger temporarily uses that directory as its working directory and
restores the caller's directory when it exits. The directory containing the
shared library is added to `LD_LIBRARY_PATH` for the duration of the run.

## Controls

| Key | Action |
| --- | --- |
| `Space` | Advance exactly one model time step and refresh the fields |
| `1` | Display water level (`s1`, metres) |
| `2` | Display velocity magnitude (`ucmag`, metres/second) |
| `3` | Display water depth (`hs`, metres) |
| `A` | Toggle velocity arrows while the velocity field is selected |
| `Escape` or `Q` | Close the window and finalize the model |

The window starts with the mesh in a neutral color. The first `Space` press
loads the fields for the resulting time step. Changing the selected field does
not advance the simulation. The background is black; the debugger uses Courier
New when installed and a monospace fallback otherwise.

## Supported scope

The first version displays 2D flow cells. It uses `flowelemnode`, `xk`, and
`yk` for mesh polygons, and `s1`, `ucmag`, `hs`, `ucx`, and `ucy` for fields
and velocity arrows. Unsupported or incompatible BMI array shapes are reported
as errors rather than being silently reshaped. 1D-only and 3D layouts are not
supported.

## Tests

The unit tests use a fake BMI model and Pygame's headless video driver, so they
do not require a Delft3D build or a model case:

```bash
python -m pytest
```

For a manual integration smoke test, run the command above with a real
`.mdu` file and the matching `libdflowfm.so`, then step the model and switch
between the three fields.
