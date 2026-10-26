# Unit tests for Stripe payments
# Created by Mattie Edozie - 10/26/26
#
# These tests don't need a database or internet.
# "mock.patch" swaps a real function for a fake one during a test, so we can
# pretend the database or Stripe answered without actually calling them.
#
# Run: python -m unittest backend.tests.test_stripe_payment -v

import hashlib
import hmac
import json
import os
import sys
import time
import unittest
from unittest import mock

# Let the tests import files from the backend folder
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from flask import Flask

from controllers.checkout_controller import checkout_bp
from services import checkout_service, payment_service

FAKE_WEBHOOK_SECRET = "whsec_test_secret"


def fake_order(status="PENDING_PAYMENT", user_id=42):
    """An order like the one get_order_by_id returns."""
    return {
        "id": 7,
        "user_id": user_id,
        "confirmation_number": "VAULT-261026-ABC123",
        "total_amount": 50.0,
        "order_status": status,
        "stripe_session_id": "cs_test_123",
    }


def fake_stripe_session(session_id="cs_test_123", payment_status="paid", amount_total=5000, order_id="7"):
    """What Stripe tells us about a payment. 5000 cents = $50.00, which matches fake_order."""
    return {
        "id": session_id,
        "payment_status": payment_status,
        "amount_total": amount_total,
        "metadata": {"order_id": order_id},
    }


def fake_webhook_message(event_type, stripe_session):
    """A webhook message in the same format Stripe sends."""
    return json.dumps({
        "id": "evt_test_1",
        "object": "event",
        "type": event_type,
        "data": {"object": stripe_session},
    })


def sign(message, secret=FAKE_WEBHOOK_SECRET):
    """
    Signs a message the same way Stripe does, so we can test the real signature check.
    The signature is a hash of the time + message, made with the secret.
    """
    timestamp = str(int(time.time()))
    signature = hmac.new(secret.encode(), (timestamp + "." + message).encode(), hashlib.sha256).hexdigest()
    return "t=" + timestamp + ",v1=" + signature


class TestDollarsToCents(unittest.TestCase):

    def test_converts_dollars_to_cents(self):
        self.assertEqual(payment_service.dollars_to_cents(50), 5000)
        self.assertEqual(payment_service.dollars_to_cents("12.5"), 1250)

    def test_rounds_correctly(self):
        # In Python, 19.99 * 100 is 1998.9999..., so we have to round
        self.assertEqual(payment_service.dollars_to_cents(19.99), 1999)


# The most important rules: when is an order allowed to become PAID?
@mock.patch.object(payment_service, "fulfill_paid_order")
@mock.patch.object(payment_service, "mark_order_paid", return_value=True)
@mock.patch.object(payment_service, "get_order_by_id", side_effect=lambda order_id: fake_order())
class TestMarkPaidIfStripeConfirms(unittest.TestCase):
    # The decorators above give every test 3 fakes, in this order:
    # get_order (fake database lookup), mark_paid (fake database update), fulfill (fake stock update)
    # side_effect=lambda... makes get_order hand back a brand new fake order on every call.

    def test_paid_payment_marks_order_paid(self, get_order, mark_paid, fulfill):
        order = payment_service.mark_paid_if_stripe_confirms(fake_stripe_session())

        mark_paid.assert_called_once_with(7)
        fulfill.assert_called_once()
        self.assertEqual(order["order_status"], "PAID")

    def test_unpaid_payment_stays_pending(self, get_order, mark_paid, fulfill):
        order = payment_service.mark_paid_if_stripe_confirms(fake_stripe_session(payment_status="unpaid"))

        mark_paid.assert_not_called()
        fulfill.assert_not_called()
        self.assertEqual(order["order_status"], "PENDING_PAYMENT")

    def test_payment_for_a_different_order_is_ignored(self, get_order, mark_paid, fulfill):
        payment_service.mark_paid_if_stripe_confirms(fake_stripe_session(session_id="cs_someone_else"))

        mark_paid.assert_not_called()

    def test_wrong_amount_is_ignored(self, get_order, mark_paid, fulfill):
        # $1.00 paid for a $50.00 order
        payment_service.mark_paid_if_stripe_confirms(fake_stripe_session(amount_total=100))

        mark_paid.assert_not_called()

    def test_missing_order_id_returns_none(self, get_order, mark_paid, fulfill):
        result = payment_service.mark_paid_if_stripe_confirms(fake_stripe_session(order_id=None))

        self.assertIsNone(result)
        mark_paid.assert_not_called()

    def test_order_that_does_not_exist_returns_none(self, get_order, mark_paid, fulfill):
        get_order.side_effect = lambda order_id: None

        self.assertIsNone(payment_service.mark_paid_if_stripe_confirms(fake_stripe_session()))
        mark_paid.assert_not_called()

    def test_already_paid_order_is_not_fulfilled_twice(self, get_order, mark_paid, fulfill):
        # mark_order_paid says False when the order was already PAID (Stripe told us twice)
        mark_paid.return_value = False

        payment_service.mark_paid_if_stripe_confirms(fake_stripe_session())

        fulfill.assert_not_called()


class TestStartStripeCheckout(unittest.TestCase):

    @mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_fake"})
    @mock.patch.object(payment_service, "set_order_stripe_session")
    @mock.patch.object(payment_service.stripe.checkout.Session, "create")
    def test_makes_payment_page_and_saves_its_id(self, stripe_create, save_session_id):
        # Pretend Stripe made a payment page
        stripe_create.return_value = mock.Mock(id="cs_test_123", url="https://checkout.stripe.com/pay/cs_test_123")
        order = {"id": 7, "confirmation_number": "VAULT-1", "buyer_email": "buyer@hamptonu.edu"}
        items = [
            {"item_name": "Hoodie", "selected_size": "M", "price_at_purchase": 20.0, "quantity": 2},
            {"item_name": "Hat", "selected_size": None, "price_at_purchase": 10.0, "quantity": 1},
        ]

        url = payment_service.start_stripe_checkout(order, items, "http://localhost:5000")

        # We get Stripe's link back and save the session id on the order
        self.assertEqual(url, "https://checkout.stripe.com/pay/cs_test_123")
        save_session_id.assert_called_once_with(7, "cs_test_123")

        # Check what we sent to Stripe
        sent = stripe_create.call_args.kwargs
        self.assertEqual(sent["metadata"], {"order_id": "7"})
        self.assertEqual(sent["line_items"][0]["price_data"]["unit_amount"], 2000)  # $20.00
        self.assertEqual(sent["line_items"][0]["price_data"]["product_data"]["name"], "Hoodie (Size M)")
        self.assertEqual(sent["line_items"][0]["quantity"], 2)
        self.assertEqual(sent["line_items"][1]["price_data"]["product_data"]["name"], "Hat")
        self.assertIn("{CHECKOUT_SESSION_ID}", sent["success_url"])
        self.assertEqual(sent["cancel_url"], "http://localhost:5000/checkout?canceled=1")


@mock.patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": FAKE_WEBHOOK_SECRET})
@mock.patch.object(payment_service, "mark_paid_if_stripe_confirms")
class TestHandleStripeWebhook(unittest.TestCase):

    def test_real_stripe_message_is_accepted(self, mark_paid):
        message = fake_webhook_message("checkout.session.completed", fake_stripe_session())

        payment_service.handle_stripe_webhook(message, sign(message))

        # It passed the payment on as a normal dictionary
        passed_in = mark_paid.call_args.args[0]
        self.assertEqual(passed_in["id"], "cs_test_123")
        self.assertEqual(passed_in["metadata"]["order_id"], "7")

    def test_delayed_payment_success_is_also_accepted(self, mark_paid):
        message = fake_webhook_message("checkout.session.async_payment_succeeded", fake_stripe_session())

        payment_service.handle_stripe_webhook(message, sign(message))

        mark_paid.assert_called_once()

    def test_other_message_types_are_ignored(self, mark_paid):
        message = fake_webhook_message("checkout.session.expired", fake_stripe_session(payment_status="unpaid"))

        payment_service.handle_stripe_webhook(message, sign(message))

        mark_paid.assert_not_called()

    def test_fake_message_is_rejected(self, mark_paid):
        message = fake_webhook_message("checkout.session.completed", fake_stripe_session())

        # Signed with the wrong secret, like someone pretending to be Stripe
        with self.assertRaises(Exception):
            payment_service.handle_stripe_webhook(message, sign(message, secret="whsec_wrong"))
        mark_paid.assert_not_called()


class TestCheckPaymentOnReturn(unittest.TestCase):

    @mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_fake"})
    @mock.patch.object(payment_service, "mark_paid_if_stripe_confirms", return_value=fake_order(user_id=999))
    @mock.patch.object(payment_service.stripe.checkout.Session, "retrieve")
    def test_cannot_see_someone_elses_order(self, stripe_retrieve, mark_paid):
        stripe_retrieve.return_value = mock.Mock(to_dict=lambda: fake_stripe_session())

        # User 42 asks about an order that belongs to user 999
        with self.assertRaises(Exception):
            payment_service.check_payment_on_return("cs_test_123", 42)


class TestCreatePendingOrder(unittest.TestCase):
    BUYER = {
        "first_name": "Ada", "last_name": "Lovelace", "email": "ada@hamptonu.edu",
        "contact": "555-0100", "meeting_location": "Student Center",
    }
    CART = [{"id": 3, "name": "Hoodie", "price": "20.00", "quantity": 2, "size": "M"}]

    def setUp(self):
        # Fake every database function checkout_service uses
        names = ["check_listing_availability", "create_order", "create_order_item",
                 "update_listing_size_inventory", "clear_cart_for_user", "remove_purchased_from_wishlist"]
        self.fakes = {}
        for name in names:
            patcher = mock.patch.object(checkout_service, name)
            self.fakes[name] = patcher.start()
            self.addCleanup(patcher.stop)  # put the real function back after the test
        self.fakes["create_order"].return_value = {"id": 7}

    def test_order_is_saved_as_pending_payment(self):
        result = checkout_service.create_pending_order(42, self.CART, self.BUYER)

        saved = self.fakes["create_order"].call_args.kwargs
        self.assertEqual(saved["order_status"], "PENDING_PAYMENT")
        self.assertEqual(saved["total_amount"], 40.0)  # 2 x $20
        self.assertEqual(result["total_amount"], 40.0)

    def test_nothing_changes_before_payment(self):
        checkout_service.create_pending_order(42, self.CART, self.BUYER)

        # Stock, cart and wishlist must NOT change until Stripe confirms
        self.fakes["update_listing_size_inventory"].assert_not_called()
        self.fakes["clear_cart_for_user"].assert_not_called()
        self.fakes["remove_purchased_from_wishlist"].assert_not_called()

    def test_missing_buyer_details_are_rejected(self):
        buyer_with_no_email = dict(self.BUYER, email="")

        with self.assertRaises(Exception):
            checkout_service.create_pending_order(42, self.CART, buyer_with_no_email)
        self.fakes["create_order"].assert_not_called()


class TestFulfillPaidOrder(unittest.TestCase):

    @mock.patch.object(checkout_service, "remove_purchased_from_wishlist")
    @mock.patch.object(checkout_service, "clear_cart_for_user")
    @mock.patch.object(checkout_service, "update_listing_size_inventory")
    @mock.patch.object(checkout_service, "get_order_items_by_order_id")
    def test_updates_stock_cart_and_wishlist(self, get_items, update_stock, clear_cart, remove_wishlist):
        get_items.return_value = [
            {"listing_id": 3, "selected_size": "M", "quantity": 2},
            {"listing_id": 4, "selected_size": None, "quantity": 1},  # no size, so no stock change
        ]

        checkout_service.fulfill_paid_order({"id": 7, "user_id": 42})

        update_stock.assert_called_once_with(3, "M", 2)
        clear_cart.assert_called_once_with(42)
        remove_wishlist.assert_called_once_with(42, [3, 4])


# These tests call the real Flask routes with a fake logged-in user
class TestCheckoutRoutes(unittest.TestCase):

    def setUp(self):
        app = Flask(__name__)
        app.secret_key = "test-only"
        app.register_blueprint(checkout_bp, url_prefix="/api")
        self.client = app.test_client()

    def log_in_with_one_item_in_cart(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 42
            sess["cart"] = [{"id": 3, "name": "Hoodie", "price": 20, "quantity": 1}]

    def cart_size(self):
        with self.client.session_transaction() as sess:
            return len(sess["cart"])

    def test_must_be_logged_in(self):
        res = self.client.post("/api/checkout/complete", json={})
        self.assertEqual(res.status_code, 401)

    @mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": ""})
    @mock.patch("controllers.checkout_controller.create_pending_order")
    def test_no_stripe_key_means_no_order_saved(self, create_pending):
        self.log_in_with_one_item_in_cart()

        res = self.client.post("/api/checkout/complete", json={})

        self.assertEqual(res.status_code, 503)
        create_pending.assert_not_called()

    @mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_fake"})
    @mock.patch("controllers.checkout_controller.start_stripe_checkout", return_value="https://checkout.stripe.com/pay/x")
    @mock.patch("controllers.checkout_controller.create_pending_order")
    def test_returns_stripe_link_and_keeps_cart(self, create_pending, start_checkout):
        create_pending.return_value = {"confirmation_number": "VAULT-1", "order": {"id": 7}, "order_items": []}
        self.log_in_with_one_item_in_cart()

        res = self.client.post("/api/checkout/complete", json={})

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["checkout_url"], "https://checkout.stripe.com/pay/x")
        self.assertEqual(self.cart_size(), 1)  # cart stays until the order is paid

    @mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_fake"})
    @mock.patch("controllers.checkout_controller.start_stripe_checkout", side_effect=Exception("Stripe is down"))
    @mock.patch("controllers.checkout_controller.create_pending_order")
    def test_stripe_down_shows_error(self, create_pending, start_checkout):
        create_pending.return_value = {"confirmation_number": "VAULT-1", "order": {"id": 7}, "order_items": []}
        self.log_in_with_one_item_in_cart()

        res = self.client.post("/api/checkout/complete", json={})

        self.assertEqual(res.status_code, 502)

    @mock.patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": FAKE_WEBHOOK_SECRET})
    @mock.patch.object(payment_service, "mark_paid_if_stripe_confirms")
    def test_webhook_rejects_fake_message(self, mark_paid):
        message = fake_webhook_message("checkout.session.completed", fake_stripe_session())

        res = self.client.post("/api/stripe/webhook", data=message, headers={"Stripe-Signature": "t=1,v1=fake"})

        self.assertEqual(res.status_code, 400)
        mark_paid.assert_not_called()

    @mock.patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": FAKE_WEBHOOK_SECRET})
    @mock.patch.object(payment_service, "mark_paid_if_stripe_confirms")
    def test_webhook_accepts_real_message(self, mark_paid):
        message = fake_webhook_message("checkout.session.completed", fake_stripe_session())

        res = self.client.post("/api/stripe/webhook", data=message, headers={"Stripe-Signature": sign(message)})

        self.assertEqual(res.status_code, 200)
        mark_paid.assert_called_once()

    @mock.patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": ""})
    def test_webhook_without_secret_is_an_error(self):
        res = self.client.post("/api/stripe/webhook", data="{}")
        self.assertEqual(res.status_code, 500)

    @mock.patch("controllers.checkout_controller.check_payment_on_return", return_value=fake_order(status="PAID"))
    def test_return_page_empties_cart_when_paid(self, check_payment):
        self.log_in_with_one_item_in_cart()

        res = self.client.get("/api/checkout/confirm?session_id=cs_test_123")

        self.assertEqual(res.get_json()["order_status"], "PAID")
        self.assertEqual(self.cart_size(), 0)

    @mock.patch("controllers.checkout_controller.check_payment_on_return", return_value=fake_order())
    def test_return_page_keeps_cart_when_not_paid(self, check_payment):
        self.log_in_with_one_item_in_cart()

        res = self.client.get("/api/checkout/confirm?session_id=cs_test_123")

        self.assertEqual(res.get_json()["order_status"], "PENDING_PAYMENT")
        self.assertEqual(self.cart_size(), 1)


if __name__ == "__main__":
    unittest.main()
