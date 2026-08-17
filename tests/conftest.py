from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def schema_dir() -> Path:
    """Directory holding types.yaml and Folder-layout.yaml."""
    return REPO_ROOT
