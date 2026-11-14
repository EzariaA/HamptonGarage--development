# Hampton Garage - Iteration 4
# Mattie Edozie - HG-119 returns page
# Unit tests for GET /returns/my, which feeds the "My Returns" list
# (loading and "No returns yet" empty states) on the returns page.
# Login is set through the session only (no X-User-Id header).
# The database is mocked, so these tests do not need the test database.

import os
import sys
import unittest
from datetime import datetime
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

MODEL = "services.return_service.get_returns_by_user"

USER_ID = 42
OTHER_USER_ID = 99
RETURN_ROW = {
    "id": 1,
    "order_number": "HG-1001",
    "reason": "Wrong size",
    "has_damage": False,
    "status": "pending",
    "created_at": datetime(2026, 11, 10, 14, 30),
}


class TestMyReturnsRoute(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with patch("app.create_vault_tables"):
            from app import create_app
            cls.app = create_app()
        cls.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app.test_client()

    def _login(self, user_id=USER_ID, role="user"):
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["role"] = role

    @patch(MODEL)
    def test_my_returns_requires_login(self, get_returns):
        response = self.client.get("/returns/my")

        self.assertEqual(response.status_code, 401)
        get_returns.assert_not_called()

    @patch(MODEL, return_value=[RETURN_ROW])
    def test_my_returns_lists_my_returns(self, get_returns):
        self._login()

        response = self.client.get("/returns/my")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["order_number"], "HG-1001")
        self.assertEqual(data[0]["status"], "pending")
        get_returns.assert_called_once_with(USER_ID)

    @patch(MODEL, return_value=[])
    def test_my_returns_empty_list_when_no_returns(self, get_returns):
        # The page shows "No returns yet." when this list is empty
        self._login()

        response = self.client.get("/returns/my")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    @patch(MODEL, return_value=[RETURN_ROW])
    def test_my_returns_dates_are_iso_text(self, get_returns):
        self._login()

        response = self.client.get("/returns/my")

        self.assertEqual(response.get_json()[0]["created_at"], "2026-11-10T14:30:00")

    @patch(MODEL, return_value=[])
    def test_my_returns_ignores_fake_user_header(self, get_returns):
        # Logged in as USER_ID but claims to be someone else in a header
        self._login()

        self.client.get("/returns/my", headers={"X-User-Id": str(OTHER_USER_ID), "X-User-Role": "admin"})

        get_returns.assert_called_once_with(USER_ID)

    @patch(MODEL, side_effect=Exception("database down"))
    def test_my_returns_database_error_returns_500(self, get_returns):
        self._login()

        response = self.client.get("/returns/my")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()["error"], "Could not load your returns.")
        # The internal error text is not sent to the browser
        self.assertNotIn("database down", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
