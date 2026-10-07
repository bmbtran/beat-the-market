import os
from pathlib import Path

import pytest

# Every test runs with a readonly cache: any attempted paid/network call through the cache fails.
os.environ["MF_CACHE_MODE"] = "readonly"

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _readonly_and_isolated_state(tmp_path, monkeypatch):
    monkeypatch.setenv("MF_CACHE_MODE", "readonly")
    monkeypatch.setenv("MF_STATE_DIR", str(tmp_path / "state"))
    yield


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES
