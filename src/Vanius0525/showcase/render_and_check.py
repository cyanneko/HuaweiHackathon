"""Validate the current concise demonstration; see render_and_check_v2.py for the long edition."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name("check_demo.py")),run_name="__main__")
