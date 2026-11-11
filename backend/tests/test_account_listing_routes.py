# Hampton Garage - Iteration 4
# Mattie Edozie - HG-119 account page
# Unit tests for the two listing routes the account page calls:
#   GET    /api/listings/my
#   DELETE /api/listings/<listing_id>
# Login is set through the session only (no X-User-Id header).
# The database is mocked, so these tests do not need the test database.

import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

CTRL = "controllers.listing_controller"
SVC = "services.listing_service"

USER_ID = 42
OTHER_USER_ID = 99
STOREFRONT = {"id": 5, "owner_id": USER_ID}
LISTING = {"id": 7, "storefront_id": 5, "status": "ACTIVE"}


class TestAccountListingRoutes(unittest.TestCase):

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

    # GET /api/listings/my

    def test_my_listings_requires_login(self):
        response = self.client.get("/api/listings/my")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json(), {"error": "Unauthorized: please log in"})

    @patch(f"{CTRL}.get_listings_for_storefront_with_options_service")
    @patch(f"{CTRL}.get_my_storefront_service")
    def test_my_listings_returns_listings_for_my_storefront(self, get_store, get_listings):
        get_store.return_value = STOREFRONT
        get_listings.return_value = [{"id": 7, "title": "Hampton Hoodie"}]
        self._login()
        response = self.client.get("/api/listings/my")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [{"id": 7, "title": "Hampton Hoodie"}])
        get_listings.assert_called_once_with(5, include_deleted=False)

    @patch(f"{CTRL}.get_listings_for_storefront_with_options_service")
    @patch(f"{CTRL}.get_my_storefront_service")
    def test_my_listings_without_storefront_returns_empty_list(self, get_store, get_listings):
        get_store.return_value = None
        self._login()
        response = self.client.get("/api/listings/my")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])
        get_listings.assert_not_called()

    @patch(f"{CTRL}.get_listings_for_storefront_with_options_service")
    @patch(f"{CTRL}.get_my_storefront_service")
    def test_my_listings_include_deleted_flag(self, get_store, get_listings):
        get_store.return_value = STOREFRONT
        get_listings.return_value = []
        self._login()
        self.client.get("/api/listings/my?include_deleted=true")
        get_listings.assert_called_once_with(5, include_deleted=True)

    @patch(f"{CTRL}.get_listings_for_storefront_with_options_service")
    @patch(f"{CTRL}.get_my_storefront_service")
    def test_my_listings_ignores_fake_user_header(self, get_store, get_listings):
        get_store.return_value = STOREFRONT
        get_listings.return_value = []
        self._login()
        self.client.get("/api/listings/my", headers={"X-User-Id": str(OTHER_USER_ID)})
        current_user = get_store.call_args[0][0]
        self.assertEqual(current_user["id"], USER_ID)

    @patch(f"{CTRL}.get_my_storefront_service")
    def test_my_listings_service_error_returns_400(self, get_store):
        get_store.side_effect = Exception("database unavailable")
        self._login()
        response = self.client.get("/api/listings/my")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "database unavailable"})

    # DELETE /api/listings/<listing_id>

    @patch(f"{SVC}.soft_delete_listing")
    def test_delete_listing_requires_login(self, soft_delete):
        response = self.client.delete("/api/listings/7")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json(), {"error": "Unauthorized: please log in"})
        soft_delete.assert_not_called()

    @patch(f"{SVC}.soft_delete_listing")
    @patch(f"{SVC}.get_storefront_by_id")
    @patch(f"{SVC}.get_listing_by_id")
    def test_delete_own_listing_succeeds(self, get_listing, get_store, soft_delete):
        get_listing.return_value = LISTING
        get_store.return_value = STOREFRONT
        soft_delete.return_value = {"id": 7, "status": "DELETED"}
        self._login()
        response = self.client.delete("/api/listings/7")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"id": 7, "status": "DELETED"})
        soft_delete.assert_called_once_with(7)

    @patch(f"{SVC}.soft_delete_listing")
    @patch(f"{SVC}.get_storefront_by_id")
    @patch(f"{SVC}.get_listing_by_id")
    def test_delete_someone_elses_listing_is_forbidden(self, get_listing, get_store, soft_delete):
        get_listing.return_value = LISTING
        get_store.return_value = {"id": 5, "owner_id": OTHER_USER_ID}
        self._login()
        response = self.client.delete("/api/listings/7")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json(), {"error": "Unauthorized action."})
        soft_delete.assert_not_called()

    @patch(f"{SVC}.soft_delete_listing")
    @patch(f"{SVC}.get_storefront_by_id")
    @patch(f"{SVC}.get_listing_by_id")
    def test_admin_can_delete_any_listing(self, get_listing, get_store, soft_delete):
        get_listing.return_value = LISTING
        get_store.return_value = {"id": 5, "owner_id": OTHER_USER_ID}
        soft_delete.return_value = {"id": 7, "status": "DELETED"}
        self._login(role="admin")
        response = self.client.delete("/api/listings/7")
        self.assertEqual(response.status_code, 200)
        soft_delete.assert_called_once_with(7)

    @patch(f"{SVC}.soft_delete_listing")
    @patch(f"{SVC}.get_listing_by_id")
    def test_delete_missing_listing_returns_404(self, get_listing, soft_delete):
        get_listing.return_value = None
        self._login()
        response = self.client.delete("/api/listings/7")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {"error": "Listing not found."})
        soft_delete.assert_not_called()

    @patch(f"{SVC}.soft_delete_listing")
    @patch(f"{SVC}.get_storefront_by_id")
    @patch(f"{SVC}.get_listing_by_id")
    def test_delete_listing_with_missing_storefront_returns_404(self, get_listing, get_store, soft_delete):
        get_listing.return_value = LISTING
        get_store.return_value = None
        self._login()
        response = self.client.delete("/api/listings/7")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {"error": "Storefront not found for this listing."})
        soft_delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
