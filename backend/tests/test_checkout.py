# Hampton Garage
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
 
CTRL = "controllers.checkout_controller"
 
BUYER = {
    "first_name": "Test",
    "last_name": "Buyer",
    "email": "buyer@my.hamptonu.edu",
    "contact": "757-555-0100",
    "meeting_location": "Student Center",
}
# The cart says $1.00 on purpose: the charge must use the database price instead.
CART = [{"id": 7, "name": "Hampton Hoodie", "price": 1.00, "quantity": 2, "size": "M"}]
USER_ID = 42
 
 
class TestStripeCheckout(unittest.TestCase):
 
    @classmethod
    def setUpClass(cls):
        with patch("app.create_vault_tables"):
            from app import create_app
            cls.app = create_app()
        cls.app.config["TESTING"] = True
 
    def setUp(self):
        self.client = self.app.test_client()
 
    def _login(self, cart=None, pending_buyer=None):
        with self.client.session_transaction() as sess:
            sess["user_id"] = USER_ID
            sess["cart"] = list(cart) if cart is not None else []
            if pending_buyer is not None:
                sess["pending_buyer"] = pending_buyer
 
    def _mock_db(self, existing_row=None):
        conn = MagicMock()
        cur = conn.cursor.return_value
        cur.fetchone.return_value = existing_row
        return conn, cur
 
    def _stripe_session(self, paid=True, user_id=USER_ID):
        s = MagicMock()
        s.payment_status = "paid" if paid else "unpaid"
        s.metadata.to_dict.return_value = {"user_id": str(user_id)}
        return s
 
    # /api/checkout/create-session 
 
    def test_create_session_requires_login(self):
        res = self.client.post("/api/checkout/create-session", json=BUYER)
        self.assertEqual(res.status_code, 401)
 
    def test_create_session_rejects_empty_cart(self):
        self._login(cart=[])
        res = self.client.post("/api/checkout/create-session", json=BUYER)
        self.assertEqual(res.status_code, 400)
 
    def test_create_session_rejects_missing_field(self):
        self._login(cart=CART)
        incomplete = dict(BUYER, meeting_location="")
        with patch(f"{CTRL}.stripe") as stripe_mock:
            res = self.client.post("/api/checkout/create-session", json=incomplete)
        self.assertEqual(res.status_code, 400)
        stripe_mock.checkout.Session.create.assert_not_called()
 
    @patch(f"{CTRL}.check_listing_availability")
    @patch(f"{CTRL}.get_listing_by_id", return_value={"id": 7, "price": 25.00})
    @patch(f"{CTRL}.stripe")
    def test_create_session_returns_stripe_url_with_database_price(self, stripe_mock, _listing, _avail):
        stripe_mock.checkout.Session.create.return_value = MagicMock(url="https://checkout.stripe.test/abc")
        self._login(cart=CART)
 
        res = self.client.post("/api/checkout/create-session", json=BUYER)
 
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["url"], "https://checkout.stripe.test/abc")
        kwargs = stripe_mock.checkout.Session.create.call_args.kwargs
        item = kwargs["line_items"][0]
        self.assertEqual(item["price_data"]["unit_amount"], 2500)  # $25.00 from DB, not $1.00 from cart
        self.assertEqual(item["quantity"], 2)
        self.assertEqual(kwargs["metadata"]["user_id"], str(USER_ID))
        with self.client.session_transaction() as sess:
            self.assertEqual(sess["pending_buyer"]["email"], BUYER["email"])
 
    @patch(f"{CTRL}.check_listing_availability")
    @patch(f"{CTRL}.get_listing_by_id", return_value=None)
    @patch(f"{CTRL}.stripe")
    def test_create_session_rejects_removed_listing(self, stripe_mock, _listing, _avail):
        self._login(cart=CART)
        res = self.client.post("/api/checkout/create-session", json=BUYER)
        self.assertEqual(res.status_code, 400)
        stripe_mock.checkout.Session.create.assert_not_called()
 
    @patch(f"{CTRL}.check_listing_availability", side_effect=Exception("Only 1 left in stock."))
    @patch(f"{CTRL}.stripe")
    def test_create_session_rejects_unavailable_item(self, stripe_mock, _avail):
        self._login(cart=CART)
        res = self.client.post("/api/checkout/create-session", json=BUYER)
        self.assertEqual(res.status_code, 400)
        self.assertIn("stock", res.get_json()["error"])
        stripe_mock.checkout.Session.create.assert_not_called()
 
    # /api/checkout/success 
 
    def test_success_without_login_redirects_to_checkout(self):
        res = self.client.get("/api/checkout/success?session_id=cs_test_1")
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers["Location"].endswith("/checkout"))
 
    @patch(f"{CTRL}.complete_transaction_from_session",
           return_value={"confirmation_number": "VAULT-261027-ABC123"})
    @patch(f"{CTRL}.stripe")
    @patch(f"{CTRL}.get_connection")
    def test_success_creates_order_when_paid(self, get_conn, stripe_mock, complete_tx):
        conn, cur = self._mock_db(existing_row=None)
        get_conn.return_value = conn
        stripe_mock.checkout.Session.retrieve.return_value = self._stripe_session(paid=True)
        self._login(cart=CART, pending_buyer=BUYER)
 
        res = self.client.get("/api/checkout/success?session_id=cs_test_1")
 
        self.assertEqual(res.status_code, 302)
        self.assertIn("/order-confirmation?conf=VAULT-261027-ABC123", res.headers["Location"])
        complete_tx.assert_called_once_with(USER_ID, CART, BUYER)
        update_sql, update_args = cur.execute.call_args_list[-1].args
        self.assertIn("UPDATE orders", update_sql)
        self.assertEqual(update_args, ("cs_test_1", "VAULT-261027-ABC123"))
        conn.commit.assert_called_once()
        with self.client.session_transaction() as sess:
            self.assertEqual(sess["cart"], [])
 
    @patch(f"{CTRL}.complete_transaction_from_session")
    @patch(f"{CTRL}.stripe")
    @patch(f"{CTRL}.get_connection")
    def test_success_does_not_create_order_when_unpaid(self, get_conn, stripe_mock, complete_tx):
        get_conn.return_value, _ = self._mock_db(existing_row=None)
        stripe_mock.checkout.Session.retrieve.return_value = self._stripe_session(paid=False)
        self._login(cart=CART, pending_buyer=BUYER)
 
        res = self.client.get("/api/checkout/success?session_id=cs_test_1")
 
        self.assertTrue(res.headers["Location"].endswith("/checkout"))
        complete_tx.assert_not_called()
 
    @patch(f"{CTRL}.complete_transaction_from_session")
    @patch(f"{CTRL}.stripe")
    @patch(f"{CTRL}.get_connection")
    def test_success_rejects_session_from_another_user(self, get_conn, stripe_mock, complete_tx):
        get_conn.return_value, _ = self._mock_db(existing_row=None)
        stripe_mock.checkout.Session.retrieve.return_value = self._stripe_session(paid=True, user_id=999)
        self._login(cart=CART, pending_buyer=BUYER)
 
        res = self.client.get("/api/checkout/success?session_id=cs_test_1")
 
        self.assertTrue(res.headers["Location"].endswith("/checkout"))
        complete_tx.assert_not_called()
 
    @patch(f"{CTRL}.complete_transaction_from_session")
    @patch(f"{CTRL}.stripe")
    @patch(f"{CTRL}.get_connection")
    def test_success_refresh_does_not_create_duplicate_order(self, get_conn, stripe_mock, complete_tx):
        get_conn.return_value, _ = self._mock_db(existing_row=("VAULT-261027-ABC123",))
        self._login(cart=CART, pending_buyer=BUYER)
 
        res = self.client.get("/api/checkout/success?session_id=cs_test_1")
 
        self.assertIn("/order-confirmation?conf=VAULT-261027-ABC123", res.headers["Location"])
        complete_tx.assert_not_called()
        stripe_mock.checkout.Session.retrieve.assert_not_called()
 
 
if __name__ == "__main__":
    unittest.main()