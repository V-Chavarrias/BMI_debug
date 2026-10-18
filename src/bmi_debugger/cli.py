"""Command-line entry point for the D-Flow FM BMI debugger."""

import argparse
from pathlib import Path
from collections.abc import Sequence

from .runner import run_debugger


def build_parser() -> argparse.ArgumentParser:
    """Create the debugger command-line parser."""
    parser = argparse.ArgumentParser(
        description="Step a 2D D-Flow FM BMI model and inspect its fields."
    )
    parser.add_argument(
        "--mdu",
        type=Path,
        required=True,
        help="path to the D-Flow FM model input (.mdu) file",
    )
    parser.add_argument(
        "--library",
        type=Path,
        required=True,
        help="path to the D-Flow FM BMI shared library (for example libdflowfm.so)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse input paths and launch the debugger."""
    args = build_parser().parse_args(argv)
    run_debugger(args.mdu, args.library)
    return 0
