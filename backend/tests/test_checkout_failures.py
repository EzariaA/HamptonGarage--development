# Hampton Garage
# AI assistance: Claude (Anthropic) helped draft these tests.
# Ezaria Alexander reviewed every test, ran them, and edited them to match the app.
import os
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
CART = [{"id": 7, "name": "Hampton Hoodie", "price": 25.00, "quantity": 2, "size": "M"}]
USER_ID = 42
SESSION_ID = "cs_test_failure_1"


class TestCheckoutFailures(unittest.TestCase):

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

    def _paid_stripe_session(self):
        s = MagicMock()
        s.payment_status = "paid"
        s.metadata.to_dict.return_value = {"user_id": str(USER_ID)}
        return s

    def _empty_db(self):
        """A fake database connection where no order exists yet for this Stripe session."""
        conn = MagicMock()
        conn.cursor.return_value.fetchone.return_value = None
        return conn

    # ---------- Cancelled payment ----------

    @patch(f"{CTRL}.check_listing_availability")
    @patch(f"{CTRL}.get_listing_by_id", return_value={"id": 7, "price": 25.00})
    @patch(f"{CTRL}.stripe")
    def test_cancel_url_carries_the_cancelled_flag(self, stripe_mock, _listing, _avail):
        stripe_mock.checkout.Session.create.return_value = MagicMock(url="https://checkout.stripe.test/abc")
        self._login(cart=CART)

        res = self.client.post("/api/checkout/create-session", json=BUYER)

        self.assertEqual(res.status_code, 200)
        cancel_url = stripe_mock.checkout.Session.create.call_args.kwargs["cancel_url"]
        self.assertTrue(cancel_url.endswith("/checkout?status=cancelled"), cancel_url)

    # ---------- Charged but no order ----------

    @patch(f"{CTRL}.complete_transaction_from_session", side_effect=Exception("Item sold out"))
    @patch(f"{CTRL}.stripe")
    @patch(f"{CTRL}.get_connection")
    def test_paid_but_order_fails_sends_buyer_back_with_a_reference(self, get_conn, stripe_mock, _complete):
        get_conn.return_value = self._empty_db()
        stripe_mock.checkout.Session.retrieve.return_value = self._paid_stripe_session()
        self._login(cart=CART, pending_buyer=BUYER)

        with self.assertLogs(CTRL, level="ERROR"):
            res = self.client.get(f"/api/checkout/success?session_id={SESSION_ID}")

        self.assertEqual(res.status_code, 302)
        self.assertTrue(
            res.headers["Location"].endswith(f"/checkout?status=order_failed&ref={SESSION_ID}"),
            res.headers["Location"],
        )

    @patch(f"{CTRL}.complete_transaction_from_session", side_effect=Exception("Item sold out"))
    @patch(f"{CTRL}.stripe")
    @patch(f"{CTRL}.get_connection")
    def test_paid_but_order_fails_logs_the_user_and_stripe_session(self, get_conn, stripe_mock, _complete):
        get_conn.return_value = self._empty_db()
        stripe_mock.checkout.Session.retrieve.return_value = self._paid_stripe_session()
        self._login(cart=CART, pending_buyer=BUYER)

        with self.assertLogs(CTRL, level="ERROR") as logs:
            self.client.get(f"/api/checkout/success?session_id={SESSION_ID}")

        message = "\n".join(logs.output)
        self.assertIn(SESSION_ID, message)
        self.assertIn(str(USER_ID), message)

    @patch(f"{CTRL}.complete_transaction_from_session", side_effect=Exception("Item sold out"))
    @patch(f"{CTRL}.stripe")
    @patch(f"{CTRL}.get_connection")
    def test_paid_but_order_fails_keeps_the_cart(self, get_conn, stripe_mock, _complete):
        get_conn.return_value = self._empty_db()
        stripe_mock.checkout.Session.retrieve.return_value = self._paid_stripe_session()
        self._login(cart=CART, pending_buyer=BUYER)

        with self.assertLogs(CTRL, level="ERROR"):
            self.client.get(f"/api/checkout/success?session_id={SESSION_ID}")

        with self.client.session_transaction() as sess:
            self.assertEqual(sess["cart"], CART)


if __name__ == "__main__":
    unittest.main()
