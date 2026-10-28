# Unit tests for the wishlist feature (existing code by Elali McNair, tests by Mattie Edozie - 10/26/26)
#
# These tests don't need a database. "mock.patch" swaps the real database
# functions for fake ones, so we can pretend the database answered.
#
# What's tested:
#   services/wishlist_service.py      - the wishlist rules (add, view, remove, check)
#   controllers/wishlist_controller.py - the /api/wishlist routes
#   models/wishlist_model.py           - the SQL functions (with a fake database connection)
#
# Run: python -m unittest backend.tests.test_wishlist_unit -v

import os
import sys
import unittest
from unittest import mock

# Let the tests import files from the backend folder
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from flask import Flask

from controllers.wishlist_controller import wishlist_bp
from models import wishlist_model
from services import wishlist_service
from services.wishlist_service import WishlistService


# ________________________________________________________
# SERVICE TESTS (services/wishlist_service.py)
# ________________________________________________________

class TestAddItemToWishlist(unittest.TestCase):

    @mock.patch.object(wishlist_service, "add_to_wishlist", return_value={"id": 1, "user_id": 42, "listing_id": 3})
    @mock.patch.object(wishlist_service, "get_listing_by_id", return_value={"id": 3, "title": "Hoodie"})
    def test_add_new_item_succeeds(self, get_listing, add):
        success, message = WishlistService().add_item_to_wishlist(42, 3)

        self.assertTrue(success)
        self.assertEqual(message, "Item added to wishlist")
        add.assert_called_once_with(42, 3)

    @mock.patch.object(wishlist_service, "add_to_wishlist")
    @mock.patch.object(wishlist_service, "get_listing_by_id", return_value=None)
    def test_add_listing_that_does_not_exist_fails(self, get_listing, add):
        success, message = WishlistService().add_item_to_wishlist(42, 999)

        self.assertFalse(success)
        self.assertEqual(message, "Listing not found")
        add.assert_not_called()  # never touches the wishlist table

    @mock.patch.object(wishlist_service, "add_to_wishlist", return_value=None)
    @mock.patch.object(wishlist_service, "get_listing_by_id", return_value={"id": 3})
    def test_add_same_item_twice_fails(self, get_listing, add):
        # add_to_wishlist returns None when the item is already there
        success, message = WishlistService().add_item_to_wishlist(42, 3)

        self.assertFalse(success)
        self.assertEqual(message, "Item already in wishlist")

    @mock.patch.object(wishlist_service, "add_to_wishlist", side_effect=Exception("database is down"))
    @mock.patch.object(wishlist_service, "get_listing_by_id", return_value={"id": 3})
    def test_add_database_error_is_handled(self, get_listing, add):
        success, message = WishlistService().add_item_to_wishlist(42, 3)

        self.assertFalse(success)
        self.assertIn("database is down", message)


class TestOtherWishlistServiceFunctions(unittest.TestCase):

    @mock.patch.object(wishlist_service, "get_wishlist_by_user_id", return_value=[{"id": 1}, {"id": 2}])
    def test_get_wishlist_returns_items(self, get_wishlist):
        success, items = WishlistService().get_user_wishlist(42)

        self.assertTrue(success)
        self.assertEqual(len(items), 2)

    @mock.patch.object(wishlist_service, "remove_from_wishlist", return_value=True)
    def test_remove_item_succeeds(self, remove):
        success, message = WishlistService().remove_item_from_wishlist(42, 3)

        self.assertTrue(success)
        self.assertEqual(message, "Item removed from wishlist")

    @mock.patch.object(wishlist_service, "remove_from_wishlist", return_value=False)
    def test_remove_item_not_in_wishlist_fails(self, remove):
        success, message = WishlistService().remove_item_from_wishlist(42, 3)

        self.assertFalse(success)
        self.assertEqual(message, "Item not found in wishlist")

    @mock.patch.object(wishlist_service, "is_in_wishlist", return_value=True)
    def test_check_item_in_wishlist(self, is_in):
        success, in_wishlist = WishlistService().check_item_in_wishlist(42, 3)

        self.assertTrue(success)
        self.assertTrue(in_wishlist)

    @mock.patch.object(wishlist_service, "get_wishlist_item_by_id", return_value=None)
    def test_details_for_missing_item_fails(self, get_item):
        success, message = WishlistService().get_wishlist_item_details(55)

        self.assertFalse(success)
        self.assertEqual(message, "Wishlist item not found")


# ________________________________________________________
# ROUTE TESTS (controllers/wishlist_controller.py)
# The wishlist routes know who you are from the X-User-Id header.
# ________________________________________________________

class TestWishlistRoutes(unittest.TestCase):

    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(wishlist_bp)
        self.client = app.test_client()
        self.logged_in = {"X-User-Id": "42"}

    def test_add_without_user_is_unauthorized(self):
        res = self.client.post("/api/wishlist", json={"listing_id": 3})
        self.assertEqual(res.status_code, 401)

    def test_add_without_listing_id_is_rejected(self):
        res = self.client.post("/api/wishlist", json={}, headers=self.logged_in)
        self.assertEqual(res.status_code, 400)

    def test_add_with_text_listing_id_is_rejected(self):
        res = self.client.post("/api/wishlist", json={"listing_id": "3"}, headers=self.logged_in)
        self.assertEqual(res.status_code, 400)

    @mock.patch("controllers.wishlist_controller.wishlist_service.add_item_to_wishlist",
                return_value=(True, "Item added to wishlist"))
    def test_add_item_returns_201(self, add):
        res = self.client.post("/api/wishlist", json={"listing_id": 3}, headers=self.logged_in)

        self.assertEqual(res.status_code, 201)
        add.assert_called_once_with(42, 3)

    @mock.patch("controllers.wishlist_controller.wishlist_service.get_user_wishlist",
                return_value=(True, [{"id": 1, "listing_id": 3}]))
    def test_get_wishlist_returns_items(self, get_wishlist):
        res = self.client.get("/api/wishlist", headers=self.logged_in)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.get_json()["wishlist"]), 1)

    @mock.patch("controllers.wishlist_controller.wishlist_service.remove_item_from_wishlist",
                return_value=(False, "Item not found in wishlist"))
    def test_remove_missing_item_returns_404(self, remove):
        res = self.client.delete("/api/wishlist/3", headers=self.logged_in)
        self.assertEqual(res.status_code, 404)

    @mock.patch("controllers.wishlist_controller.wishlist_service.get_wishlist_item_details",
                return_value=(True, {"id": 55, "user_id": 999}))
    def test_cannot_see_someone_elses_wishlist_item(self, get_details):
        # Item 55 belongs to user 999, but user 42 is asking
        res = self.client.get("/api/wishlist/items/55", headers=self.logged_in)
        self.assertEqual(res.status_code, 403)


# ________________________________________________________
# DATABASE FUNCTION TESTS (models/wishlist_model.py)
# A fake connection stands in for the real database.
# ________________________________________________________

def fake_database(fetchone=None, rowcount=0):
    """Makes a fake connection + cursor. fetchone/rowcount are what the 'database' answers."""
    cursor = mock.Mock()
    cursor.fetchone.return_value = fetchone
    cursor.rowcount = rowcount
    conn = mock.Mock()
    conn.cursor.return_value = cursor
    return conn, cursor


class TestWishlistModel(unittest.TestCase):

    def test_add_returns_the_new_row(self):
        conn, cursor = fake_database(fetchone=(1, 42, 3, "2026-10-26"))
        with mock.patch.object(wishlist_model, "get_connection", return_value=conn):
            item = wishlist_model.add_to_wishlist(42, 3)

        self.assertEqual(item, {"id": 1, "user_id": 42, "listing_id": 3, "added_date": "2026-10-26"})
        conn.commit.assert_called_once()

    def test_add_duplicate_returns_none(self):
        # ON CONFLICT DO NOTHING means the database gives back no row for a duplicate
        conn, cursor = fake_database(fetchone=None)
        with mock.patch.object(wishlist_model, "get_connection", return_value=conn):
            self.assertIsNone(wishlist_model.add_to_wishlist(42, 3))

    def test_remove_reports_if_anything_was_deleted(self):
        conn, cursor = fake_database(rowcount=1)
        with mock.patch.object(wishlist_model, "get_connection", return_value=conn):
            self.assertTrue(wishlist_model.remove_from_wishlist(42, 3))

        conn, cursor = fake_database(rowcount=0)
        with mock.patch.object(wishlist_model, "get_connection", return_value=conn):
            self.assertFalse(wishlist_model.remove_from_wishlist(42, 3))

    def test_is_in_wishlist(self):
        conn, cursor = fake_database(fetchone=(1,))
        with mock.patch.object(wishlist_model, "get_connection", return_value=conn):
            self.assertTrue(wishlist_model.is_in_wishlist(42, 3))

        conn, cursor = fake_database(fetchone=None)
        with mock.patch.object(wishlist_model, "get_connection", return_value=conn):
            self.assertFalse(wishlist_model.is_in_wishlist(42, 3))

    def test_queries_use_the_values_safely(self):
        # The user id and listing id must be passed as values, never pasted into the SQL text
        conn, cursor = fake_database(rowcount=1)
        with mock.patch.object(wishlist_model, "get_connection", return_value=conn):
            wishlist_model.remove_from_wishlist(42, 3)

        sql, values = cursor.execute.call_args.args
        self.assertEqual(values, (42, 3))
        self.assertNotIn("42", sql)


if __name__ == "__main__":
    unittest.main()
