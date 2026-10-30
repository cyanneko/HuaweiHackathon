"""Compatibility entry point for the current R81 presentation checks."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name("render_and_check_v2.py")), run_name="__main__")
