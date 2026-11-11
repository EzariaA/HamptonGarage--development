# Hampton Garage
# Iteration 3 unit tests (HG-101) - Ava Bell - 10/27/26
# Cart and orders, including the Stripe payment fields on orders.
#   - complete_transaction_from_session: order total and price_at_purchase come from the
#     listings table (what Stripe charged), not the session cart (HG-100)
#   - order summary: only the buyer can see their order
#   - persistent cart (cart_items): load and clear
#   - payment fields: stripe_session_id and payment_status are saved when Stripe confirms payment
# No real database or Stripe account is used; both are replaced with mocks.

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from services import checkout_service
from services.auth_services import AuthService

SVC = "services.checkout_service"
CTRL = "controllers.checkout_controller"
USER_ID = 42

BUYER = {
    "first_name": "Test",
    "last_name": "Buyer",
    "email": "buyer@my.hamptonu.edu",
    "contact": "757-555-0100",
    "meeting_location": "Student Center",
}


def fake_order(**overrides):
    order = {"id": 501, "user_id": USER_ID, "confirmation_number": "VAULT-261027-ABC123",
             "total_amount": 0, "order_status": "PENDING_PAYMENT"}
    order.update(overrides)
    return order


class TestOrderTotalsUseDatabasePrices(unittest.TestCase):
    """complete_transaction_from_session (checkout_service.py).

    Updated by Ava Bell - Iteration 4 (HG-114): main now saves the order, items and stock
    together in place_order_with_inventory() (Kyle Lewis), so these tests check what is
    passed to that function instead of create_order / create_order_item.
    """

    def setUp(self):
        patches = {
            "conf": patch(f"{SVC}._generate_confirmation_number", return_value="VAULT-261027-ABC123"),
            "place": patch(f"{SVC}.place_order_with_inventory",
                           side_effect=lambda **kw: {"order": fake_order(total_amount=kw["total_amount"]),
                                                     "order_items": kw["cart_items"]}),
            "get_listing": patch(f"{SVC}.get_listing_by_id"),
            "clear_cart": patch(f"{SVC}.clear_cart_for_user"),
            "wishlist": patch(f"{SVC}.remove_purchased_from_wishlist"),
        }
        self.mocks = {name: p.start() for name, p in patches.items()}
        for p in patches.values():
            self.addCleanup(p.stop)

    def test_total_and_item_prices_come_from_listings_not_cart(self):
        # The cart says $1.00, but the listing costs $25.00 in the database (what Stripe charged).
        self.mocks["get_listing"].return_value = {"id": 7, "price": 25.00}
        cart = [{"id": 7, "name": "Hampton Hoodie", "price": 1.00, "quantity": 2, "size": "M"}]

        result = checkout_service.complete_transaction_from_session(USER_ID, cart, BUYER)

        self.assertEqual(result["total_amount"], 50.00)
        kwargs = self.mocks["place"].call_args.kwargs
        self.assertEqual(kwargs["total_amount"], 50.00)
        self.assertEqual(kwargs["cart_items"][0]["price"], 25.00)
        self.assertEqual(kwargs["cart_items"][0]["quantity"], 2)
        self.assertEqual(kwargs["cart_items"][0]["size"], "M")
        self.mocks["clear_cart"].assert_called_once_with(USER_ID)

    def test_total_adds_several_items_at_database_prices(self):
        prices = {7: 25.00, 8: 12.50}
        self.mocks["get_listing"].side_effect = lambda listing_id: {"id": listing_id, "price": prices[listing_id]}
        cart = [
            {"id": 7, "name": "Hoodie", "price": 1.00, "quantity": 1, "size": "M"},
            {"id": 8, "name": "Cap", "price": 1.00, "quantity": 3, "size": None},
        ]

        result = checkout_service.complete_transaction_from_session(USER_ID, cart, BUYER)

        self.assertEqual(result["total_amount"], 62.50)  # 25.00 + 3 x 12.50
        self.assertEqual(len(result["order_items"]), 2)

    def test_empty_cart_is_rejected(self):
        with self.assertRaises(Exception) as ctx:
            checkout_service.complete_transaction_from_session(USER_ID, [], BUYER)
        self.assertIn("Cart is empty", str(ctx.exception))
        self.mocks["place"].assert_not_called()

    def test_missing_buyer_detail_is_rejected(self):
        self.mocks["get_listing"].return_value = {"id": 7, "price": 25.00}
        buyer = dict(BUYER, meeting_location="   ")
        cart = [{"id": 7, "name": "Hoodie", "price": 25.00, "quantity": 1, "size": "M"}]
        with self.assertRaises(Exception) as ctx:
            checkout_service.complete_transaction_from_session(USER_ID, cart, buyer)
        self.assertIn("All buyer details are required", str(ctx.exception))
        self.mocks["place"].assert_not_called()

    def test_removed_listing_is_rejected(self):
        self.mocks["get_listing"].return_value = None
        cart = [{"id": 7, "name": "Hoodie", "price": 25.00, "quantity": 1, "size": "M"}]
        with self.assertRaises(Exception) as ctx:
            checkout_service.complete_transaction_from_session(USER_ID, cart, BUYER)
        self.assertIn("no longer available", str(ctx.exception))
        self.mocks["place"].assert_not_called()

    def test_sold_out_item_is_rejected(self):
        # place_order_with_inventory raises when stock runs out; no cart clear happens.
        self.mocks["get_listing"].return_value = {"id": 7, "price": 25.00}
        self.mocks["place"].side_effect = Exception("Only 1 left in stock.")
        cart = [{"id": 7, "name": "Hoodie", "price": 25.00, "quantity": 2, "size": "M"}]
        with self.assertRaises(Exception) as ctx:
            checkout_service.complete_transaction_from_session(USER_ID, cart, BUYER)
        self.assertIn("Only 1 left", str(ctx.exception))
        self.mocks["clear_cart"].assert_not_called()


class TestOrderSummary(unittest.TestCase):
    """get_order_summary_service (checkout_service.py): existing order code."""

    @patch(f"{SVC}.get_order_items_by_order_id", return_value=[{"item_name": "Hoodie"}])
    @patch(f"{SVC}.get_order_by_confirmation", return_value=fake_order())
    def test_buyer_sees_own_order_and_items(self, _order, _items):
        result = checkout_service.get_order_summary_service("VAULT-261027-ABC123", USER_ID)
        self.assertEqual(result["order"]["id"], 501)
        self.assertEqual(result["order_items"], [{"item_name": "Hoodie"}])

    @patch(f"{SVC}.get_order_items_by_order_id")
    @patch(f"{SVC}.get_order_by_confirmation", return_value=fake_order(user_id=99))
    def test_other_user_cannot_see_order(self, _order, get_items):
        with self.assertRaises(Exception) as ctx:
            checkout_service.get_order_summary_service("VAULT-261027-ABC123", USER_ID)
        self.assertIn("Access denied", str(ctx.exception))
        get_items.assert_not_called()

    @patch(f"{SVC}.get_order_by_confirmation", return_value=None)
    def test_unknown_confirmation_number(self, _order):
        with self.assertRaises(Exception) as ctx:
            checkout_service.get_order_summary_service("VAULT-000000-NOPE00", USER_ID)
        self.assertIn("Order not found", str(ctx.exception))


class TestPersistentCart(unittest.TestCase):
    """AuthService.get_user_cart / clear_user_cart (auth_services.py): existing cart code."""

    def setUp(self):
        self.service = AuthService()
        self.conn = MagicMock()
        self.cur = self.conn.cursor.return_value

    def test_cart_rows_load_as_items(self):
        from decimal import Decimal
        self.cur.fetchall.return_value = [(7, "Hampton Hoodie", Decimal("25.00"), 2, "M")]
        cart = self.service.get_user_cart(self.conn, USER_ID)
        self.assertEqual(cart, [{"id": 7, "name": "Hampton Hoodie", "price": 25.0, "quantity": 2, "size": "M"}])
        self.assertEqual(self.cur.execute.call_args.args[1], (USER_ID,))

    def test_cart_is_empty_when_database_fails(self):
        self.cur.execute.side_effect = Exception("connection lost")
        self.assertEqual(self.service.get_user_cart(self.conn, USER_ID), [])

    def test_clear_cart_deletes_only_this_users_items(self):
        self.service.clear_user_cart(self.conn, USER_ID)
        sql, params = self.cur.execute.call_args.args
        self.assertIn("DELETE FROM cart_items", sql)
        self.assertEqual(params, (USER_ID,))
        self.conn.commit.assert_called_once()


class TestPaymentFieldsOnOrders(unittest.TestCase):
    """/api/checkout/success saves stripe_session_id and payment_status on the order."""

    @classmethod
    def setUpClass(cls):
        with patch("app.create_vault_tables"):
            from app import create_app
            cls.app = create_app()
        cls.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = USER_ID
            sess["cart"] = [{"id": 7, "name": "Hoodie", "price": 25.00, "quantity": 1, "size": "M"}]
            sess["pending_buyer"] = BUYER

    def _stripe_session(self, paid):
        s = MagicMock()
        s.payment_status = "paid" if paid else "unpaid"
        s.metadata.to_dict.return_value = {"user_id": str(USER_ID)}
        return s

    @patch(f"{CTRL}.complete_transaction_from_session",
           return_value={"confirmation_number": "VAULT-261027-ABC123"})
    @patch(f"{CTRL}.stripe")
    @patch(f"{CTRL}.get_connection")
    def test_paid_session_saves_session_id_and_payment_status(self, get_conn, stripe_mock, _complete):
        cur = get_conn.return_value.cursor.return_value
        cur.fetchone.return_value = None  # no order yet for this session
        stripe_mock.checkout.Session.retrieve.return_value = self._stripe_session(paid=True)

        res = self.client.get("/api/checkout/success?session_id=cs_test_123")

        self.assertEqual(res.status_code, 302)
        update_sql, params = cur.execute.call_args.args
        self.assertIn("stripe_session_id", update_sql)
        self.assertIn("payment_status = 'paid'", update_sql)
        self.assertEqual(params, ("cs_test_123", "VAULT-261027-ABC123"))
        get_conn.return_value.commit.assert_called_once()

    @patch(f"{CTRL}.complete_transaction_from_session")
    @patch(f"{CTRL}.stripe")
    @patch(f"{CTRL}.get_connection")
    def test_unpaid_session_saves_nothing(self, get_conn, stripe_mock, complete_tx):
        get_conn.return_value.cursor.return_value.fetchone.return_value = None
        stripe_mock.checkout.Session.retrieve.return_value = self._stripe_session(paid=False)

        res = self.client.get("/api/checkout/success?session_id=cs_test_123")

        self.assertIn("/checkout", res.headers["Location"])
        complete_tx.assert_not_called()
        get_conn.return_value.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
