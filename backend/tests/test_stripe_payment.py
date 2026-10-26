# Unit tests for Stripe payment confirmation
# Created by Mattie Edozie - 10/26/26
# No database or internet needed: the database helpers and Stripe API calls are mocked.
# Run: python -m unittest backend.tests.test_stripe_payment

import hashlib
import hmac
import json
import os
import sys
import time
import unittest
from unittest import mock

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

import stripe
from flask import Flask

from controllers.checkout_controller import checkout_bp
from services import checkout_service, payment_service

WEBHOOK_SECRET = "whsec_test_secret"


def make_order(**overrides):
    order = {
        "id": 7,
        "user_id": 42,
        "confirmation_number": "VAULT-261026-ABC123",
        "total_amount": 50.0,
        "order_status": "PENDING_PAYMENT",
        "stripe_session_id": "cs_test_123",
    }
    order.update(overrides)
    return order


def make_session(**overrides):
    checkout_session = {
        "id": "cs_test_123",
        "payment_status": "paid",
        "amount_total": 5000,
        "metadata": {"order_id": "7"},
    }
    checkout_session.update(overrides)
    return checkout_session


def sign_payload(payload, secret=WEBHOOK_SECRET):
    """Builds a Stripe-Signature header the same way Stripe does."""
    timestamp = int(time.time())
    signed = f"{timestamp}.{payload}".encode()
    signature = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def webhook_event(event_type, checkout_session):
    return json.dumps({
        "id": "evt_test_1",
        "object": "event",
        "type": event_type,
        "data": {"object": dict(checkout_session, object="checkout.session")},
    })


class TestToCents(unittest.TestCase):
    def test_converts_dollars_to_cents(self):
        self.assertEqual(payment_service.to_cents(50), 5000)
        self.assertEqual(payment_service.to_cents("12.5"), 1250)

    def test_rounds_float_error(self):
        # 19.99 * 100 is 1998.9999... in floating point
        self.assertEqual(payment_service.to_cents(19.99), 1999)


class TestConfirmPaidSession(unittest.TestCase):
    def setUp(self):
        patcher_get = mock.patch.object(payment_service, "get_order_by_id")
        patcher_mark = mock.patch.object(payment_service, "mark_order_paid")
        patcher_fulfill = mock.patch.object(payment_service, "fulfill_paid_order")
        self.get_order = patcher_get.start()
        self.mark_paid = patcher_mark.start()
        self.fulfill = patcher_fulfill.start()
        for p in (patcher_get, patcher_mark, patcher_fulfill):
            self.addCleanup(p.stop)
        self.get_order.return_value = make_order()
        self.mark_paid.return_value = True

    def test_paid_session_marks_order_paid_and_fulfills(self):
        order = payment_service.confirm_paid_session(make_session())

        self.mark_paid.assert_called_once_with(7)
        self.fulfill.assert_called_once()
        self.assertEqual(order["order_status"], "PAID")

    def test_unpaid_session_leaves_order_pending(self):
        order = payment_service.confirm_paid_session(make_session(payment_status="unpaid"))

        self.mark_paid.assert_not_called()
        self.fulfill.assert_not_called()
        self.assertEqual(order["order_status"], "PENDING_PAYMENT")

    def test_session_for_a_different_order_is_ignored(self):
        payment_service.confirm_paid_session(make_session(id="cs_someone_else"))

        self.mark_paid.assert_not_called()
        self.fulfill.assert_not_called()

    def test_wrong_amount_is_ignored(self):
        payment_service.confirm_paid_session(make_session(amount_total=100))

        self.mark_paid.assert_not_called()
        self.fulfill.assert_not_called()

    def test_missing_order_id_returns_none(self):
        self.assertIsNone(payment_service.confirm_paid_session(make_session(metadata={})))
        self.get_order.assert_not_called()

    def test_unknown_order_returns_none(self):
        self.get_order.return_value = None

        self.assertIsNone(payment_service.confirm_paid_session(make_session()))
        self.mark_paid.assert_not_called()

    def test_already_paid_order_is_not_fulfilled_twice(self):
        # mark_order_paid returns False when the order was already PAID
        self.mark_paid.return_value = False

        payment_service.confirm_paid_session(make_session())

        self.fulfill.assert_not_called()


class TestStartStripeCheckout(unittest.TestCase):
    @mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_fake"})
    @mock.patch.object(payment_service, "set_order_stripe_session")
    @mock.patch.object(payment_service.stripe.checkout.Session, "create")
    def test_creates_session_and_saves_its_id(self, create, set_session):
        create.return_value = mock.Mock(id="cs_test_123", url="https://checkout.stripe.com/c/pay/cs_test_123")
        order = make_order(buyer_email="buyer@hamptonu.edu")
        items = [
            {"item_name": "Hoodie", "selected_size": "M", "price_at_purchase": 20.0, "quantity": 2},
            {"item_name": "Hat", "selected_size": None, "price_at_purchase": 10.0, "quantity": 1},
        ]

        url = payment_service.start_stripe_checkout(order, items, "http://localhost:5000")

        self.assertEqual(url, "https://checkout.stripe.com/c/pay/cs_test_123")
        set_session.assert_called_once_with(7, "cs_test_123")

        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["mode"], "payment")
        self.assertEqual(kwargs["metadata"], {"order_id": "7"})
        self.assertEqual(kwargs["line_items"][0]["price_data"]["unit_amount"], 2000)
        self.assertEqual(kwargs["line_items"][0]["price_data"]["product_data"]["name"], "Hoodie (Size M)")
        self.assertEqual(kwargs["line_items"][0]["quantity"], 2)
        self.assertEqual(kwargs["line_items"][1]["price_data"]["product_data"]["name"], "Hat")
        self.assertIn("{CHECKOUT_SESSION_ID}", kwargs["success_url"])
        self.assertTrue(kwargs["cancel_url"].startswith("http://localhost:5000/checkout"))

    @mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": ""})
    def test_missing_key_raises_config_error(self):
        with self.assertRaises(payment_service.PaymentConfigError):
            payment_service.start_stripe_checkout(make_order(), [], "http://localhost:5000")


class TestHandleStripeWebhook(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(payment_service, "confirm_paid_session")
        self.confirm = patcher.start()
        self.addCleanup(patcher.stop)
        env = mock.patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": WEBHOOK_SECRET})
        env.start()
        self.addCleanup(env.stop)

    def test_signed_completed_event_confirms_session(self):
        payload = webhook_event("checkout.session.completed", make_session())

        event_type = payment_service.handle_stripe_webhook(payload, sign_payload(payload))

        self.assertEqual(event_type, "checkout.session.completed")
        session_arg = self.confirm.call_args.args[0]
        self.assertIsInstance(session_arg, dict)
        self.assertEqual(session_arg["id"], "cs_test_123")
        self.assertEqual(session_arg["metadata"]["order_id"], "7")

    def test_async_payment_succeeded_also_confirms(self):
        payload = webhook_event("checkout.session.async_payment_succeeded", make_session())

        payment_service.handle_stripe_webhook(payload, sign_payload(payload))

        self.confirm.assert_called_once()

    def test_other_events_are_ignored(self):
        payload = webhook_event("checkout.session.expired", make_session(payment_status="unpaid"))

        payment_service.handle_stripe_webhook(payload, sign_payload(payload))

        self.confirm.assert_not_called()

    def test_bad_signature_is_rejected(self):
        payload = webhook_event("checkout.session.completed", make_session())

        with self.assertRaises(stripe.SignatureVerificationError):
            payment_service.handle_stripe_webhook(payload, sign_payload(payload, secret="whsec_wrong"))
        self.confirm.assert_not_called()

    def test_missing_secret_raises_config_error(self):
        payload = webhook_event("checkout.session.completed", make_session())
        with mock.patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": ""}):
            with self.assertRaises(payment_service.PaymentConfigError):
                payment_service.handle_stripe_webhook(payload, sign_payload(payload))


class TestCreatePendingOrder(unittest.TestCase):
    BUYER = {
        "first_name": "Ada", "last_name": "Lovelace", "email": "ada@hamptonu.edu",
        "contact": "555-0100", "meeting_location": "Student Center",
    }
    CART = [{"id": 3, "name": "Hoodie", "price": "20.00", "quantity": 2, "size": "M"}]

    def setUp(self):
        self.mocks = {}
        for name in ("check_listing_availability", "create_order", "create_order_item",
                     "update_listing_size_inventory", "clear_cart_for_user", "remove_purchased_from_wishlist"):
            patcher = mock.patch.object(checkout_service, name)
            self.mocks[name] = patcher.start()
            self.addCleanup(patcher.stop)
        self.mocks["create_order"].return_value = {"id": 7}

    def test_order_is_saved_as_pending_payment(self):
        result = checkout_service.create_pending_order(42, self.CART, self.BUYER)

        kwargs = self.mocks["create_order"].call_args.kwargs
        self.assertEqual(kwargs["order_status"], "PENDING_PAYMENT")
        self.assertEqual(kwargs["total_amount"], 40.0)
        self.assertEqual(result["total_amount"], 40.0)
        self.mocks["create_order_item"].assert_called_once()

    def test_nothing_is_fulfilled_before_payment(self):
        checkout_service.create_pending_order(42, self.CART, self.BUYER)

        self.mocks["update_listing_size_inventory"].assert_not_called()
        self.mocks["clear_cart_for_user"].assert_not_called()
        self.mocks["remove_purchased_from_wishlist"].assert_not_called()

    def test_missing_buyer_details_raise(self):
        with self.assertRaises(Exception):
            checkout_service.create_pending_order(42, self.CART, dict(self.BUYER, email=""))
        self.mocks["create_order"].assert_not_called()


class TestFulfillPaidOrder(unittest.TestCase):
    @mock.patch.object(checkout_service, "remove_purchased_from_wishlist")
    @mock.patch.object(checkout_service, "clear_cart_for_user")
    @mock.patch.object(checkout_service, "update_listing_size_inventory")
    @mock.patch.object(checkout_service, "get_order_items_by_order_id")
    def test_updates_inventory_cart_and_wishlist(self, get_items, update_inventory, clear_cart, remove_wishlist):
        get_items.return_value = [
            {"listing_id": 3, "selected_size": "M", "quantity": 2},
            {"listing_id": 4, "selected_size": None, "quantity": 1},
        ]

        checkout_service.fulfill_paid_order({"id": 7, "user_id": 42})

        update_inventory.assert_called_once_with(3, "M", 2)
        clear_cart.assert_called_once_with(42)
        remove_wishlist.assert_called_once_with(42, [3, 4])


class TestCheckoutRoutes(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.secret_key = "test-only"
        app.config["TESTING"] = True
        app.register_blueprint(checkout_bp, url_prefix="/api")
        self.client = app.test_client()

    def login(self, cart=None):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 42
            sess["cart"] = cart if cart is not None else [{"id": 3, "name": "Hoodie", "price": 20, "quantity": 1}]

    def test_complete_requires_login(self):
        self.assertEqual(self.client.post("/api/checkout/complete", json={}).status_code, 401)

    @mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": ""})
    @mock.patch("controllers.checkout_controller.create_pending_order")
    def test_complete_without_stripe_key_saves_nothing(self, create_pending):
        self.login()

        res = self.client.post("/api/checkout/complete", json={})

        self.assertEqual(res.status_code, 503)
        create_pending.assert_not_called()

    @mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_fake"})
    @mock.patch("controllers.checkout_controller.start_stripe_checkout")
    @mock.patch("controllers.checkout_controller.create_pending_order")
    def test_complete_returns_stripe_url_and_keeps_cart(self, create_pending, start_checkout):
        create_pending.return_value = {
            "confirmation_number": "VAULT-1", "order": {"id": 7}, "order_items": [], "total_amount": 20.0,
        }
        start_checkout.return_value = "https://checkout.stripe.com/c/pay/cs_test_123"
        self.login()

        res = self.client.post("/api/checkout/complete", json={})

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["checkout_url"], "https://checkout.stripe.com/c/pay/cs_test_123")
        # The cart is only cleared once Stripe confirms the payment
        with self.client.session_transaction() as sess:
            self.assertEqual(len(sess["cart"]), 1)

    @mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_fake"})
    @mock.patch("controllers.checkout_controller.start_stripe_checkout")
    @mock.patch("controllers.checkout_controller.create_pending_order")
    def test_complete_handles_stripe_errors(self, create_pending, start_checkout):
        create_pending.return_value = {
            "confirmation_number": "VAULT-1", "order": {"id": 7}, "order_items": [], "total_amount": 20.0,
        }
        start_checkout.side_effect = stripe.APIConnectionError("network down")
        self.login()

        self.assertEqual(self.client.post("/api/checkout/complete", json={}).status_code, 502)

    @mock.patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": WEBHOOK_SECRET})
    @mock.patch.object(payment_service, "confirm_paid_session")
    def test_webhook_rejects_bad_signature(self, confirm):
        payload = webhook_event("checkout.session.completed", make_session())

        res = self.client.post("/api/stripe/webhook", data=payload,
                               headers={"Stripe-Signature": "t=1,v1=bad"})

        self.assertEqual(res.status_code, 400)
        confirm.assert_not_called()

    @mock.patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": WEBHOOK_SECRET})
    @mock.patch.object(payment_service, "confirm_paid_session")
    def test_webhook_accepts_signed_event(self, confirm):
        payload = webhook_event("checkout.session.completed", make_session())

        res = self.client.post("/api/stripe/webhook", data=payload,
                               headers={"Stripe-Signature": sign_payload(payload)})

        self.assertEqual(res.status_code, 200)
        confirm.assert_called_once()

    @mock.patch("controllers.checkout_controller.confirm_session_for_user")
    def test_confirm_clears_cart_when_paid(self, confirm_for_user):
        confirm_for_user.return_value = make_order(order_status="PAID")
        self.login()

        res = self.client.get("/api/checkout/confirm?session_id=cs_test_123")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["order_status"], "PAID")
        with self.client.session_transaction() as sess:
            self.assertEqual(sess["cart"], [])

    @mock.patch("controllers.checkout_controller.confirm_session_for_user")
    def test_confirm_keeps_cart_while_pending(self, confirm_for_user):
        confirm_for_user.return_value = make_order()
        self.login()

        res = self.client.get("/api/checkout/confirm?session_id=cs_test_123")

        self.assertEqual(res.get_json()["order_status"], "PENDING_PAYMENT")
        with self.client.session_transaction() as sess:
            self.assertEqual(len(sess["cart"]), 1)


class TestConfirmSessionForUser(unittest.TestCase):
    @mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_fake"})
    @mock.patch.object(payment_service, "confirm_paid_session")
    @mock.patch.object(payment_service.stripe.checkout.Session, "retrieve")
    def test_other_users_order_is_rejected(self, retrieve, confirm):
        retrieve.return_value = mock.Mock(to_dict=lambda: make_session())
        confirm.return_value = make_order(user_id=999)

        with self.assertRaises(Exception):
            payment_service.confirm_session_for_user("cs_test_123", 42)


if __name__ == "__main__":
    unittest.main()
