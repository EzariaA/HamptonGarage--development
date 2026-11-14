# By Elali McNair 4/19/26
# Updated by Ava Bell - Iteration 4 (HG-115):
#   - Logs in through the Flask session (session_transaction, same pattern as test_checkout.py)
#     instead of the old X-User-Id header, which the server no longer reads.
#   - Makes its own seller and storefront in the test database before each test. conftest.py
#     empties every table before each test, so the old "find an existing storefront" lookup
#     never found one and all three tests were always skipped.
#   - The image upload is mocked so no file is written to S3 or static/uploads.
#   - Added real-database checks that only the owner can update or delete a listing.
import io
import os
import sys
import unittest
import uuid
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from app import create_app
from db import get_connection # changed to 'from db' - by Makena Jelks 9/30/26
from utils.auth_utils import hash_password

S3_UPLOAD = "utils.s3.upload_image_to_s3"


def _insert_user(username):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, password, email, role) VALUES (%s, %s, %s, 'user') RETURNING id;",
            (username, hash_password("Passw0rd!"), username + "@hamptonu.edu"),
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        return user_id
    finally:
        cur.close()
        conn.close()


def _insert_storefront(owner_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO storefronts (owner_id, brand_name) VALUES (%s, 'Test Brand') RETURNING id;",
            (owner_id,),
        )
        storefront_id = cur.fetchone()[0]
        conn.commit()
        return storefront_id
    finally:
        cur.close()
        conn.close()


def _listing_status(listing_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT status, title FROM listings WHERE id = %s;", (listing_id,))
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()


class TestCreateListingFeature(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True

    def setUp(self):
        # conftest.py has already emptied the tables, so make a fresh seller and storefront.
        self.client = self.app.test_client()
        self.user_id = _insert_user("test_seller")
        self.storefront_id = _insert_storefront(self.user_id)

    def _login(self, user_id=None):
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id if user_id is not None else self.user_id
            sess["role"] = "user"

    def _create_listing(self, title):
        with patch(S3_UPLOAD, return_value="https://s3.test/listings/test_listing.png"):
            return self.client.post(
                "/api/listings/create",
                data={
                    "title": title,
                    "quantity_on_hand": "5",
                    "price": "39.99",
                    "fulfillment_type": "IN_STOCK",
                    "status": "ACTIVE",
                    "sizes_available": '["M", "L"]',
                    "listing_image": (io.BytesIO(b"fake image bytes"), "test_listing.png"),
                },
                content_type="multipart/form-data",
            )

    def test_create_listing_from_form_success(self):
        unique_title = f"TEST_CREATE_LISTING_{uuid.uuid4().hex[:8]}"
        self._login()

        response = self._create_listing(unique_title)

        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        payload = response.get_json()

        self.assertIsNotNone(payload)
        self.assertEqual(payload["title"], unique_title)
        self.assertEqual(payload["storefront_id"], self.storefront_id)
        self.assertEqual(payload["status"], "ACTIVE")
        self.assertEqual(payload["fulfillment_type"], "IN_STOCK")

        listing_id = payload["id"]

        verify_response = self.client.get(f"/api/storefronts/{self.storefront_id}/listings")
        self.assertEqual(verify_response.status_code, 200)

        listings = verify_response.get_json()
        matched = next((item for item in listings if item["id"] == listing_id), None)
        self.assertIsNotNone(matched)
        self.assertEqual(matched["title"], unique_title)

    def test_create_listing_requires_image_file(self):
        self._login()
        response = self.client.post(
            "/api/listings/create",
            data={
                "title": f"TEST_CREATE_LISTING_{uuid.uuid4().hex[:8]}",
                "quantity_on_hand": "3",
                "price": "25.00",
                "fulfillment_type": "IN_STOCK",
                "status": "ACTIVE",
                "sizes_available": '["S"]',
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400, response.get_data(as_text=True))
        # The message changed when multi-image upload was added
        self.assertIn("At least one listing image is required", response.get_data(as_text=True))

    def test_create_listing_requires_authentication(self):
        # Not logged in: no session at all
        response = self.client.post(
            f"/api/storefronts/{self.storefront_id}/listings",
            json={
                "title": "Unauthorized Listing",
                "price": 20,
                "fulfillment_type": "IN_STOCK",
                "quantity_on_hand": 2,
            },
        )

        self.assertEqual(response.status_code, 401, response.get_data(as_text=True))
        self.assertIn("Unauthorized", response.get_data(as_text=True))

    # ---------- Update and delete with a real database (added HG-115) ----------

    def test_owner_can_update_listing(self):
        self._login()
        listing_id = self._create_listing("Original Title").get_json()["id"]

        response = self.client.put(f"/api/listings/{listing_id}", json={"title": "Updated Title", "price": 45})

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(_listing_status(listing_id)[1], "Updated Title")

    def test_other_user_cannot_update_listing(self):
        self._login()
        listing_id = self._create_listing("Original Title").get_json()["id"]

        self._login(_insert_user("someone_else"))
        response = self.client.put(f"/api/listings/{listing_id}", json={"title": "Hacked"})

        self.assertEqual(response.status_code, 403, response.get_data(as_text=True))
        self.assertEqual(_listing_status(listing_id)[1], "Original Title")

    def test_owner_can_delete_listing(self):
        self._login()
        listing_id = self._create_listing("To Delete").get_json()["id"]

        response = self.client.delete(f"/api/listings/{listing_id}")

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(_listing_status(listing_id)[0], "DELETED")  # soft delete

    def test_other_user_cannot_delete_listing(self):
        self._login()
        listing_id = self._create_listing("Keep Me").get_json()["id"]

        self._login(_insert_user("someone_else"))
        response = self.client.delete(f"/api/listings/{listing_id}")

        self.assertEqual(response.status_code, 403, response.get_data(as_text=True))
        self.assertEqual(_listing_status(listing_id)[0], "ACTIVE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
