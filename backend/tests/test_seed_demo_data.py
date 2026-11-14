# Unit tests for the demo data loader (seed_demo_data.py)
# Created by Mattie Edozie - 10/26/26
#
# These tests don't need a database. FakeCursor below pretends to be the database:
# it writes down every SQL statement it gets, so the tests can check what would have been saved.
#
# Run: python -m unittest backend.tests.test_seed_demo_data -v

import os
import sys
import unittest
from unittest import mock

# Let the tests import files from the backend folder
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

import seed_demo_data


class FakeCursor:
    """
    Pretends to be a database cursor.
    existing_users: {username: user id} for users already in the "database"
    owners_with_storefront: user ids that already have a storefront
    """

    def __init__(self, existing_users=None, owners_with_storefront=None):
        self.existing_users = existing_users or {}
        self.owners_with_storefront = owners_with_storefront or []
        self.saved = []        # every (sql, values) we were given
        self.next_id = 100     # fake ids for new rows
        self.answer = None     # what fetchone() returns next

    def execute(self, sql, values=None):
        # Squash newlines and extra spaces so "INSERT INTO storefronts\n  (..." matches "INSERT INTO storefronts ("
        sql = " ".join(sql.split())
        self.saved.append((sql, values))
        self.answer = None

        if sql.startswith("SELECT id FROM users"):
            username = values[0]
            if username in self.existing_users:
                self.answer = (self.existing_users[username],)

        elif sql.startswith("SELECT id FROM storefronts"):
            owner_id = values[0]
            if owner_id in self.owners_with_storefront:
                self.answer = (1,)

        elif "RETURNING id" in sql:
            self.next_id = self.next_id + 1
            self.answer = (self.next_id,)

    def fetchone(self):
        return self.answer

    def close(self):
        pass

    def inserts_into(self, table):
        """Returns the values of every INSERT into this table."""
        found = []
        for sql, values in self.saved:
            if sql.startswith("INSERT INTO " + table + " "):
                found.append(values)
        return found


class FakeConnection:
    """Pretends to be a database connection and remembers if we saved or undid."""

    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.fake_cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


def run_seed_with(cursor):
    """Runs seed_demo_data() using our fake database instead of the real one."""
    conn = FakeConnection(cursor)
    with mock.patch.object(seed_demo_data, "get_connection", return_value=conn):
        created = seed_demo_data.seed_demo_data()
    return created, conn


def count_demo_listings():
    total = 0
    for store in seed_demo_data.DEMO_STOREFRONTS:
        total = total + len(store["listings"])
    return total


class TestSeedDemoData(unittest.TestCase):

    def test_empty_database_gets_every_demo_store(self):
        cursor = FakeCursor()

        created, conn = run_seed_with(cursor)

        self.assertEqual(created, 4)
        self.assertEqual(len(cursor.inserts_into("storefronts")), 4)
        self.assertEqual(len(cursor.inserts_into("listings")), count_demo_listings())
        self.assertEqual(len(cursor.inserts_into("listing_sizes")), count_demo_listings() * 4)  # S, M, L, XL
        self.assertTrue(conn.committed)

    def test_running_twice_adds_nothing_new(self):
        # Pretend all 4 demo owners and their storefronts are already there
        users = {"demo_nike": 1, "demo_essentials": 2, "demo_vondutch": 3, "demo_onyx": 4}
        cursor = FakeCursor(existing_users=users, owners_with_storefront=[1, 2, 3, 4])

        created, conn = run_seed_with(cursor)

        self.assertEqual(created, 0)
        self.assertEqual(cursor.inserts_into("users"), [])
        self.assertEqual(cursor.inserts_into("storefronts"), [])
        self.assertEqual(cursor.inserts_into("listings"), [])

    def test_only_missing_stores_are_added(self):
        # Only the Nike demo store is already there
        cursor = FakeCursor(existing_users={"demo_nike": 1}, owners_with_storefront=[1])

        created, conn = run_seed_with(cursor)

        self.assertEqual(created, 3)

    def test_demo_passwords_are_hashed_and_different(self):
        cursor = FakeCursor()

        run_seed_with(cursor)

        passwords = []
        for username, password, email in cursor.inserts_into("users"):
            passwords.append(password)
            self.assertTrue(password.startswith("pbkdf2:sha256"))  # hashed, not plain text
        self.assertEqual(len(set(passwords)), len(passwords))      # no two are the same

    def test_each_listing_has_one_main_picture(self):
        cursor = FakeCursor()

        run_seed_with(cursor)

        main_pictures = {}
        for listing_id, image_url, is_primary in cursor.inserts_into("listing_images"):
            if is_primary:
                main_pictures[listing_id] = main_pictures.get(listing_id, 0) + 1
        self.assertEqual(len(main_pictures), count_demo_listings())
        for count in main_pictures.values():
            self.assertEqual(count, 1)

    def test_error_undoes_everything(self):
        cursor = FakeCursor()
        cursor.execute = mock.Mock(side_effect=Exception("database is down"))
        conn = FakeConnection(cursor)

        with mock.patch.object(seed_demo_data, "get_connection", return_value=conn):
            with self.assertRaises(Exception):
                seed_demo_data.seed_demo_data()

        self.assertTrue(conn.rolled_back)
        self.assertFalse(conn.committed)

    def test_every_demo_picture_file_exists(self):
        images_folder = os.path.join(PROJECT_ROOT, "static", "images")
        for store in seed_demo_data.DEMO_STOREFRONTS:
            pictures = [store["logo"]]
            for listing in store["listings"]:
                pictures = pictures + listing["images"]

            for picture in pictures:
                path = os.path.join(images_folder, picture)
                self.assertTrue(os.path.isfile(path), "missing static/images/" + picture)

    # Added by Clarence Bostic 11/14/26 - stores with unknown categories never show on the Categories page
    def test_demo_categories_are_on_the_site_list(self):
        from services.listing_service import STOREFRONT_CATEGORIES
        for store in seed_demo_data.DEMO_STOREFRONTS:
            categories = store["categories"].split(",")
            self.assertLessEqual(len(categories), 3, store["brand_name"] + " has more than 3 categories")
            for category in categories:
                self.assertIn(category, STOREFRONT_CATEGORIES, store["brand_name"] + ": " + category)


if __name__ == "__main__":
    unittest.main()