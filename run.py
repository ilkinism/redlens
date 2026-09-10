"""Start Redlens: python run.py

The package lives under src/, so put that directory on the import path before
importing it. Without this, `python run.py` in a fresh clone fails with
ModuleNotFoundError -- the tests do not catch it because pytest.ini sets
pythonpath for them.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from redlens.server import main  # noqa: E402  (path must be set first)

if __name__ == "__main__":
    main()
