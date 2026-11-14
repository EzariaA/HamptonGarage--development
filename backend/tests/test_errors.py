# Iteration 4 unit tests - Makena Jelks
# Covers: the custom 404 and 500 pages (HG-121).
# The database is mocked, so these tests need no storefront data.

import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

CTRL = "controllers.storefront_controller"
SECRET_DETAIL = "db password xyz"


class TestErrorPages(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with patch("app.create_vault_tables"):
            from app import create_app
            cls.app = create_app()
        cls.app.config["TESTING"] = True
        # In testing mode Flask re-raises errors instead of showing the 500 page.
        # Turning this off lets the real 500 handler run, like it does on the live site.
        cls.app.config["PROPAGATE_EXCEPTIONS"] = False

        # Test-only route on this test app (app.py is not changed)
        @cls.app.route("/test-only/crash")
        def crash():
            raise RuntimeError(SECRET_DETAIL)

    def setUp(self):
        self.client = self.app.test_client()

    # 404

    def test_unknown_url_shows_404_page(self):
        res = self.client.get("/no-such-page")
        body = res.get_data(as_text=True)
        self.assertEqual(res.status_code, 404)
        self.assertIn("Page not found", body)
        self.assertIn("Page Not Found | Hampton Garage", body)
        self.assertIn("css/pages/errors.css", body)

    def test_404_page_links_back_to_storefronts(self):
        res = self.client.get("/no-such-page")
        body = res.get_data(as_text=True)
        self.assertIn('href="/storefronts"', body)
        self.assertIn("Back to storefronts", body)

    def test_non_numeric_storefront_id_shows_404_page(self):
        res = self.client.get("/storefronts/abc")
        self.assertEqual(res.status_code, 404)
        self.assertIn("Page not found", res.get_data(as_text=True))

    @patch(f"{CTRL}.get_storefront_by_id", return_value=None)
    def test_api_not_found_still_returns_json(self, _get):
        res = self.client.get("/api/storefronts/999")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.get_json(), {"error": "Storefront not found."})

    # 500

    def test_unhandled_error_shows_500_page(self):
        res = self.client.get("/test-only/crash")
        body = res.get_data(as_text=True)
        self.assertEqual(res.status_code, 500)
        self.assertIn("Something went wrong", body)
        self.assertIn("Something Went Wrong | Hampton Garage", body)

    def test_500_page_hides_error_details(self):
        res = self.client.get("/test-only/crash")
        self.assertEqual(res.status_code, 500)
        self.assertNotIn(SECRET_DETAIL, res.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
