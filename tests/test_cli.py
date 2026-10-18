"""Tests for the command-line entry point."""

from pathlib import Path

from bmi_debugger import cli


def test_cli_passes_model_and_library_paths(monkeypatch, tmp_path):
    model_input = tmp_path / "FlowFM.mdu"
    library_path = tmp_path / "libdflowfm.so"
    received: list[tuple[Path, Path]] = []
    monkeypatch.setattr(
        cli,
        "run_debugger",
        lambda model, library: received.append((model, library)),
    )

    result = cli.main(["--mdu", str(model_input), "--library", str(library_path)])

    assert result == 0
    assert received == [(model_input, library_path)]
