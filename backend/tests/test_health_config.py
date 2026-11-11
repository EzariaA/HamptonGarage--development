# backend/tests/test_health_config.py
# Created by Kyle Lewis 10/26/26 - Iteration 3
# Tests for the /health route and the app settings (Test IDs HC-1 to HC-4)

import os

import pytest

from app import create_app


# HC-1: /health says the app is running
def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


# HC-2: /health only allows GET
def test_health_rejects_post(client):
    response = client.post("/health")
    assert response.status_code == 405


# HC-3: the app won't start without a SECRET_KEY
def test_app_will_not_start_without_secret_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        create_app()


# HC-4: the tests are running in testing mode on the test database, not the real one
def test_app_uses_test_settings(app):
    assert app.config["TESTING"] == True
    assert app.secret_key == os.environ["SECRET_KEY"]
    assert os.environ["DB_NAME"].endswith("_test")
