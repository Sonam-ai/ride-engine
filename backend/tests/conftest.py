import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Starts the app (and a fresh in-memory Redis) for each test."""
    with TestClient(app) as c:
        yield c