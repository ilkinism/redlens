"""`python run.py` must work in a fresh clone.

pytest.ini puts src/ on the path for the tests, which means the suite can pass
while the documented start command fails for anyone who clones the repository.
This test runs the real command in a subprocess with PYTHONPATH stripped.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_python_run_py_starts_the_app():
    port = free_port()
    environment = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    environment["REDLENS_PORT"] = str(port)
    process = subprocess.Popen(
        [sys.executable, "run.py"], cwd=APP_ROOT, env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        deadline = time.time() + 25
        last = None
        while time.time() < deadline:
            if process.poll() is not None:
                raise AssertionError(
                    "run.py exited:\n" + (process.stdout.read() or ""))
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
                    assert json.loads(response.read())["status"] == "ok"
                    return
            except Exception as error:            # not up yet
                last = error
                time.sleep(0.25)
        raise AssertionError(f"run.py never answered on port {port}: {last}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
