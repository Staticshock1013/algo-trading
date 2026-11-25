"""Locate the repository root from a notebook or a script."""

from pathlib import Path


def repo_root() -> Path:
    """Return the directory that contains this package.

    Works when the process was started in the repo root or in ``notebooks/``.
    """
    here = Path.cwd().resolve()
    for candidate in (here, *here.parents):
        if (candidate / "src" / "paths.py").is_file():
            return candidate
    raise FileNotFoundError(
        "Could not find the repo root. Run from the repository root or from notebooks/."
    )
