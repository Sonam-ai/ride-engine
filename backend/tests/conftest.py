import os

# Must be set BEFORE the app is imported, because settings are read at import time.
os.environ["REDIS_URL"] = "memory"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SWEEP_INTERVAL_SECONDS"] = "3600"
os.environ["SURGE_INTERVAL_SECONDS"] = "3600"
os.environ["MATCHING_INTERVAL"] = "3600"
os.environ["TRIP_TICK_SECONDS"] = "3600"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture
def client():
    """Starts the app with a fresh in-memory Redis and database for each test."""
    with TestClient(app) as c:
        yield c