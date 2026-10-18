"""High-level entry point for running a debugger session."""

from pathlib import Path

from .app import DebuggerApp
from .model import DFlowFMSession


def run_debugger(model_input: str | Path, library_path: str | Path) -> None:
    """Initialize the supplied D-Flow FM model and run its interactive window."""
    with DFlowFMSession(model_input, library_path) as session:
        DebuggerApp(session).run()
