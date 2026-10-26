# Unit tests for the demo data loader
# Created by Mattie Edozie - 10/26/26
# No database needed: get_connection is replaced with a fake that records the SQL.
# Run: python -m unittest backend.tests.test_seed_demo_data

import os
import sys
import unittest
from unittest import mock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

import seed_demo_data


class FakeCursor:
    """Answers the loader's SELECTs and hands out ids for INSERT ... RETURNING id."""

    def __init__(self, existing_users=None, users_with_storefront=()):
        self.existing_users = dict(existing_users or {})
        self.users_with_storefront = set(users_with_storefront)
        self.statements = []
        self.next_id = 1000
        self._result = None

    def execute(self, sql, params=None):
        self.statements.append((" ".join(sql.split()), params))
        self._result = None
        if sql.startswith("SELECT id FROM users"):
            user_id = self.existing_users.get(params[0])
            self._result = (user_id,) if user_id else None
        elif sql.startswith("SELECT id FROM storefronts"):
            self._result = (1,) if params[0] in self.users_with_storefront else None
        elif "RETURNING id" in sql:
            self.next_id += 1
            self._result = (self.next_id,)

    def fetchone(self):
        return self._result

    def close(self):
        pass

    def inserts_into(self, table):
        return [params for sql, params in self.statements if sql.startswith(f"INSERT INTO {table} ")]


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


def run_seed(cursor):
    conn = FakeConnection(cursor)
    with mock.patch.object(seed_demo_data, "get_connection", return_value=conn):
        created = seed_demo_data.seed_demo_data()
    return created, conn


class TestSeedDemoData(unittest.TestCase):
    def test_empty_database_gets_every_storefront(self):
        cursor = FakeCursor()

        created, conn = run_seed(cursor)

        total_listings = sum(len(s["listings"]) for s in seed_demo_data.DEMO_STOREFRONTS)
        self.assertEqual(created, len(seed_demo_data.DEMO_STOREFRONTS))
        self.assertEqual(len(cursor.inserts_into("storefronts")), created)
        self.assertEqual(len(cursor.inserts_into("listings")), total_listings)
        self.assertEqual(len(cursor.inserts_into("listing_sizes")), total_listings * len(seed_demo_data.DEMO_SIZES))
        self.assertTrue(conn.committed)

    def test_takes_lock_before_writing(self):
        cursor = FakeCursor()

        run_seed(cursor)

        self.assertIn("pg_advisory_xact_lock", cursor.statements[0][0])

    def test_running_again_creates_nothing(self):
        users = {s["username"]: i for i, s in enumerate(seed_demo_data.DEMO_STOREFRONTS, start=1)}
        cursor = FakeCursor(existing_users=users, users_with_storefront=users.values())

        created, _ = run_seed(cursor)

        self.assertEqual(created, 0)
        self.assertEqual(cursor.inserts_into("users"), [])
        self.assertEqual(cursor.inserts_into("storefronts"), [])
        self.assertEqual(cursor.inserts_into("listings"), [])

    def test_only_missing_storefronts_are_added(self):
        first = seed_demo_data.DEMO_STOREFRONTS[0]["username"]
        cursor = FakeCursor(existing_users={first: 1}, users_with_storefront=[1])

        created, _ = run_seed(cursor)

        self.assertEqual(created, len(seed_demo_data.DEMO_STOREFRONTS) - 1)

    def test_demo_users_get_hashed_random_passwords(self):
        cursor = FakeCursor()

        run_seed(cursor)

        passwords = [params[1] for params in cursor.inserts_into("users")]
        self.assertTrue(all(p.startswith("pbkdf2:sha256") for p in passwords))
        self.assertEqual(len(set(passwords)), len(passwords))

    def test_one_primary_image_per_listing(self):
        cursor = FakeCursor()

        run_seed(cursor)

        primary_by_listing = {}
        for listing_id, _, is_primary in cursor.inserts_into("listing_images"):
            primary_by_listing[listing_id] = primary_by_listing.get(listing_id, 0) + int(is_primary)
        self.assertTrue(all(count == 1 for count in primary_by_listing.values()))

    def test_rolls_back_on_error(self):
        cursor = FakeCursor()
        conn = FakeConnection(cursor)
        cursor.execute = mock.Mock(side_effect=RuntimeError("db down"))

        with mock.patch.object(seed_demo_data, "get_connection", return_value=conn):
            with self.assertRaises(RuntimeError):
                seed_demo_data.seed_demo_data()
        self.assertTrue(conn.rolled_back)
        self.assertFalse(conn.committed)

    def test_every_demo_image_exists(self):
        images_dir = os.path.join(PROJECT_ROOT, "static", "images")
        for store in seed_demo_data.DEMO_STOREFRONTS:
            names = [store["logo"]] + [img for listing in store["listings"] for img in listing["images"]]
            for name in names:
                self.assertTrue(os.path.isfile(os.path.join(images_dir, name)), f"missing static/images/{name}")


if __name__ == "__main__":
    unittest.main()
