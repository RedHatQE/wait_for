"""Test configuration: ensure tests always run against the local source tree."""

from __future__ import annotations

from pathlib import Path

import wait_for

REPO_ROOT = Path(__file__).resolve().parent.parent


def pytest_configure() -> None:
    actual = Path(wait_for.__file__).resolve()
    expected_dir = REPO_ROOT / "wait_for"
    if not actual.is_relative_to(expected_dir):
        raise RuntimeError(
            f"Tests are importing wait_for from {actual}, "
            f"but expected the local source tree at {expected_dir}/. "
            "Ensure the package is installed in editable mode or PYTHONPATH includes the repo root."
        )
