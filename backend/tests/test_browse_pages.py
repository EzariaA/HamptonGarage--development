# Tests for the Recent Listings and Categories pages
# Created by Clarence Bostic - Iteration 3

import os
import sys
import unittest
 
# Let Python find app.py (project folder) and the backend modules
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)
 
from app import create_app
 
 
class TestBrowsePages(unittest.TestCase):
 
    def setUp(self):
        # Runs before every test: make a fresh app and a test client
        app = create_app()
        app.config["TESTING"] = True
        self.client = app.test_client()
 
    # ---------- The pages themselves ----------
 
    def test_recent_listings_page_loads(self):
        response = self.client.get("/recent-listings")
        self.assertEqual(response.status_code, 200)
 
    def test_categories_page_loads(self):
        response = self.client.get("/categories")
        self.assertEqual(response.status_code, 200)
 
    # ---------- GET /api/listings/recent ----------
 
    def test_recent_api_returns_listings_and_total(self):
        response = self.client.get("/api/listings/recent")
        data = response.get_json()
 
        self.assertEqual(response.status_code, 200)
        self.assertIn("listings", data)
        self.assertIn("total", data)
 
    def test_recent_api_respects_limit(self):
        # Asking for 2 should never return more than 2
        data = self.client.get("/api/listings/recent?limit=2").get_json()
        self.assertLessEqual(len(data["listings"]), 2)
 
    def test_recent_api_is_newest_first(self):
        listings = self.client.get("/api/listings/recent").get_json()["listings"]
        dates = [listing["created_at"] for listing in listings]
 
        # sorted(..., reverse=True) puts the newest date first
        self.assertEqual(dates, sorted(dates, reverse=True))
 
    def test_recent_api_only_shows_public_listings(self):
        # Shoppers should never see INACTIVE or DELETED listings
        listings = self.client.get("/api/listings/recent?limit=60").get_json()["listings"]
        for listing in listings:
            self.assertIn(listing["status"], ["ACTIVE", "SOLD_OUT"])
 
    def test_recent_api_rejects_bad_limit(self):
        response = self.client.get("/api/listings/recent?limit=abc")
        self.assertEqual(response.status_code, 400)
 
    # ---------- GET /api/listings/categories ----------
 
    def test_categories_api_returns_all_eight(self):
        response = self.client.get("/api/listings/categories")
        names = [category["name"] for category in response.get_json()]
 
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(names), 8)
        self.assertIn("Vintage", names)
 
    # ---------- GET /api/listings/categories/<category> ----------
 
    def test_category_listings_api_works(self):
        response = self.client.get("/api/listings/categories/Vintage")
        data = response.get_json()
 
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["category"], "Vintage")
        self.assertIn("listings", data)
 
    def test_category_name_is_not_case_sensitive(self):
        # "vintage" in lowercase should still find Vintage
        data = self.client.get("/api/listings/categories/vintage").get_json()
        self.assertEqual(data["category"], "Vintage")
 
    def test_unknown_category_returns_404(self):
        response = self.client.get("/api/listings/categories/Shoes")
        self.assertEqual(response.status_code, 404)
 
 
if __name__ == "__main__":
    unittest.main()