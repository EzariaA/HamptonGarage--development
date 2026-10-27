# Iteration 3 unit tests - Makena Jelks
# Covers: broken access control fix (session-only identity) and the returns feature.
# The database is mocked, so these tests run without PostgreSQL data.

import os
import sys
import unittest
from unittest.mock import patch

# Let Python find app.py (project root) and backend/ modules
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

os.environ.setdefault("SECRET_KEY", "test-secret")  # app refuses to start without one

from app import create_app
from services import return_service

FAKE_ADMIN_HEADERS = {"X-User-Id": "8", "X-User-Role": "admin"}


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def log_in_as(self, user_id, role="user"):
        """Pretend a user logged in by filling the session like login does."""
        with self.client.session_transaction() as s:
            s["user"] = f"user{user_id}"
            s["user_id"] = user_id
            s["role"] = role


# ______________________________________________________________
# ACCESS CONTROL
# ______________________________________________________________
class TestAccessControl(BaseTest):

    def test_fake_admin_header_without_login_is_rejected(self):
        """Fake X-User-Id / X-User-Role headers alone must not count as logged in."""
        response = self.client.delete("/api/listings/1", headers=FAKE_ADMIN_HEADERS)
        self.assertEqual(response.status_code, 401)

    @patch("controllers.listing_controller.delete_listing_service")
    def test_fake_admin_header_is_ignored_for_logged_in_user(self, mock_delete):
        """A logged-in regular user who sends fake admin headers is still treated as themselves."""
        mock_delete.side_effect = Exception("Unauthorized action.")
        self.log_in_as(3, role="user")

        response = self.client.delete("/api/listings/1", headers=FAKE_ADMIN_HEADERS)

        # The controller passed the REAL user from the session, not the fake headers
        current_user = mock_delete.call_args[0][0]
        self.assertEqual(current_user, {"id": 3, "role": "user"})
        self.assertEqual(response.status_code, 403)

    def test_get_current_user_reads_session_only(self):
        from utils.auth_utils import get_current_user
        with self.app.test_request_context(headers=FAKE_ADMIN_HEADERS):
            self.assertIsNone(get_current_user())          # headers alone: nobody
        with self.app.test_request_context(headers=FAKE_ADMIN_HEADERS):
            from flask import session
            session["user_id"] = 3
            session["role"] = "user"
            self.assertEqual(get_current_user(), {"id": 3, "role": "user"})


# ______________________________________________________________
# RETURNS
# ______________________________________________________________
class TestReturns(BaseTest):

    @patch("services.return_service.create_return_record")
    def test_submit_return_success(self, mock_create):
        mock_create.return_value = {"id": 1, "order_number": "HG-1001", "status": "pending"}
        self.log_in_as(3)

        response = self.client.post("/returns", data={
            "order_number": "HG-1001", "reason": "Wrong size", "has_damage": "no",
        })

        self.assertEqual(response.status_code, 201)
        # Saved under the logged-in user, as pending, with has_damage converted to False
        mock_create.assert_called_once_with(
            user_id=3, order_number="HG-1001", reason="Wrong size",
            has_damage=False, damage_image_url=None, status="pending",
        )

    def test_submit_return_requires_login(self):
        response = self.client.post("/returns", headers=FAKE_ADMIN_HEADERS,
                                    data={"order_number": "HG-1001", "reason": "x", "has_damage": "no"})
        self.assertEqual(response.status_code, 401)

    @patch("services.return_service.create_return_record")
    def test_submit_return_missing_order_number(self, mock_create):
        self.log_in_as(3)
        response = self.client.post("/returns", data={"reason": "Wrong size", "has_damage": "no"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("order_number is required", response.get_json()["error"])
        mock_create.assert_not_called()

    @patch("services.return_service.create_return_record")
    def test_submit_return_missing_reason(self, mock_create):
        self.log_in_as(3)
        response = self.client.post("/returns", data={"order_number": "HG-1001", "has_damage": "no"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("reason is required", response.get_json()["error"])
        mock_create.assert_not_called()

    @patch("services.return_service.create_return_record")
    def test_submit_return_invalid_has_damage(self, mock_create):
        self.log_in_as(3)
        response = self.client.post("/returns", data={
            "order_number": "HG-1001", "reason": "Wrong size", "has_damage": "maybe"})
        self.assertEqual(response.status_code, 400)
        mock_create.assert_not_called()

    def test_submit_return_rejects_bad_image_type(self):
        from io import BytesIO
        self.log_in_as(3)
        response = self.client.post("/returns", content_type="multipart/form-data", data={
            "order_number": "HG-1001", "reason": "Damaged", "has_damage": "yes",
            "damage_image": (BytesIO(b"not an image"), "notes.txt"),
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("Damage image must be", response.get_json()["error"])

    def test_has_damage_accepts_yes_and_no_words(self):
        self.assertTrue(return_service._normalize_has_damage("Yes"))
        self.assertFalse(return_service._normalize_has_damage("0"))

    @patch("services.return_service.update_return_status")
    def test_update_status_normalizes_valid_status(self, mock_update):
        mock_update.return_value = {"id": 1, "status": "reviewed"}
        return_service.update_return_status_service(1, "  Reviewed ")
        mock_update.assert_called_once_with(1, "reviewed")

    @patch("services.return_service.update_return_status")
    def test_update_status_rejects_invalid_status(self, mock_update):
        with self.assertRaises(Exception) as ctx:
            return_service.update_return_status_service(1, "refunded")
        self.assertIn("status must be", str(ctx.exception))
        mock_update.assert_not_called()

    @patch("services.return_service.update_return_status", return_value=None)
    def test_update_status_return_not_found(self, mock_update):
        with self.assertRaises(Exception) as ctx:
            return_service.update_return_status_service(999, "resolved")
        self.assertIn("Return not found", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
