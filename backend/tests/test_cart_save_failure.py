# Hampton Garage - Iteration 4 (K3: cart stored in two places)
# Checks that the database is the source of truth for the cart and that the session
# copy never disagrees with it, even when a database save fails.
# The database is mocked, so these tests run offline.
# AI assistance: Claude (Anthropic) helped draft these tests.
# Ezaria Alexander reviewed every test, ran them, and edited them to match the app.
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

CTRL = "controllers.auth_controller"
USER_ID = 42
LISTING_ROW = ("ACTIVE", 5, False)   # status, quantity_on_hand, is_made_to_order
ITEM_FORM = {"item_id": "7", "item_name": "Hampton Hoodie", "price": "25.00",
             "quantity": "1", "size": "M"}
SAVED_ITEM = {"id": 7, "name": "Hampton Hoodie", "price": 25.0,
              "quantity": 1, "size": "M", "cart_id": 99}


class TestCartSaveFailure(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with patch("app.create_vault_tables"):
            from app import create_app
            cls.app = create_app()
        cls.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app.test_client()

    def _login(self, cart=None):
        with self.client.session_transaction() as sess:
            sess["user"] = "buyer"
            sess["user_id"] = USER_ID
            sess["cart"] = list(cart) if cart is not None else []

    def _session_cart(self):
        with self.client.session_transaction() as sess:
            return sess.get("cart")

    def _mock_conn(self, fail_on=None, fetchone=None):
        """A fake database connection. fail_on: text that makes execute() raise."""
        conn = MagicMock()
        cur = conn.cursor.return_value
        if fetchone is not None:
            cur.fetchone.side_effect = fetchone
        if fail_on:
            def execute(sql, params=None):
                if fail_on in sql:
                    raise Exception("database is down")
            cur.execute.side_effect = execute
        return conn, cur

    # ---------- Add to cart ----------

    def test_add_saves_to_database_and_keeps_row_id_in_session(self):
        self._login()
        conn, _ = self._mock_conn(fetchone=[LISTING_ROW, (99,)])
        with patch(f"{CTRL}.get_connection", return_value=conn):
            res = self.client.post("/auth/add_to_cart", data=ITEM_FORM)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(self._session_cart()[0]["cart_id"], 99)

    def test_add_failed_save_returns_error_and_leaves_session_unchanged(self):
        self._login()
        conn, _ = self._mock_conn(fail_on="INSERT INTO cart_items", fetchone=[LISTING_ROW])
        with patch(f"{CTRL}.get_connection", return_value=conn):
            res = self.client.post("/auth/add_to_cart", data=ITEM_FORM)
        self.assertEqual(res.status_code, 500)
        self.assertIn("couldn't save your cart", res.get_json()["error"])
        self.assertEqual(self._session_cart(), [])

    # ---------- Remove from cart ----------

    def test_remove_deletes_the_exact_database_row(self):
        self._login(cart=[SAVED_ITEM])
        conn, cur = self._mock_conn()
        with patch(f"{CTRL}.get_connection", return_value=conn):
            res = self.client.post("/auth/remove_from_cart/0")
        self.assertEqual(res.status_code, 302)
        sql, params = cur.execute.call_args.args
        self.assertIn("DELETE FROM cart_items WHERE id = %s", sql)
        self.assertEqual(params, (99, USER_ID))
        self.assertEqual(self._session_cart(), [])

    def test_remove_failed_delete_keeps_the_item_in_the_session(self):
        self._login(cart=[SAVED_ITEM])
        conn, _ = self._mock_conn(fail_on="DELETE FROM cart_items")
        with patch(f"{CTRL}.get_connection", return_value=conn):
            res = self.client.post("/auth/remove_from_cart/0")
        self.assertEqual(res.status_code, 302)
        self.assertEqual(len(self._session_cart()), 1)

    # ---------- Opening the cart reloads it from the database ----------

    def test_cart_page_reloads_session_from_database(self):
        self._login(cart=[])
        conn, _ = self._mock_conn()
        with patch(f"{CTRL}.get_connection", return_value=conn), \
             patch(f"{CTRL}.service.get_user_cart", return_value=[SAVED_ITEM]):
            res = self.client.get("/auth/cart")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self._session_cart(), [SAVED_ITEM])

    def test_cart_page_keeps_session_cart_if_database_read_fails(self):
        self._login(cart=[SAVED_ITEM])
        conn, _ = self._mock_conn()
        with patch(f"{CTRL}.get_connection", return_value=conn), \
             patch(f"{CTRL}.service.get_user_cart", side_effect=Exception("database is down")):
            res = self.client.get("/auth/cart")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self._session_cart(), [SAVED_ITEM])


if __name__ == "__main__":
    unittest.main()