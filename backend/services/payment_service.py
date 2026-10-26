# The Vault Campus Marketplace
# CSC 404 Fall 26'
# Created by Mattie Edozie - 10/26/26
# Stripe Checkout payments. An order is only marked PAID after Stripe confirms it,
# either through the signed webhook or by asking Stripe directly when the buyer returns.
# Card details are entered on Stripe's page and never reach our server.
import logging
import os

import stripe

from models.checkout_model import get_order_by_id, mark_order_paid, set_order_stripe_session
from services.checkout_service import fulfill_paid_order

logger = logging.getLogger(__name__)

# Stripe events that mean a Checkout Session may now be paid
PAID_EVENT_TYPES = ("checkout.session.completed", "checkout.session.async_payment_succeeded")


class PaymentConfigError(Exception):
    """Raised when the Stripe keys are missing from the environment."""


def payments_configured():
    return bool(os.getenv("STRIPE_SECRET_KEY"))


def _use_secret_key():
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        raise PaymentConfigError("Online payments are not set up. Add STRIPE_SECRET_KEY to your .env file.")
    stripe.api_key = key


def to_cents(amount):
    """Stripe takes amounts in cents: 12.5 -> 1250."""
    return int(round(float(amount) * 100))


def start_stripe_checkout(order, order_items, base_url):
    """Creates a Stripe Checkout Session for the order and returns the Stripe payment page URL."""
    _use_secret_key()

    line_items = []
    for item in order_items:
        name = item.get("item_name") or "Item"
        if item.get("selected_size"):
            name = f"{name} (Size {item['selected_size']})"
        line_items.append({
            "price_data": {
                "currency": "usd",
                "product_data": {"name": name},
                "unit_amount": to_cents(item["price_at_purchase"]),
            },
            "quantity": int(item["quantity"]),
        })

    checkout_session = stripe.checkout.Session.create(
        mode="payment",
        line_items=line_items,
        customer_email=order.get("buyer_email"),
        client_reference_id=order["confirmation_number"],
        metadata={"order_id": str(order["id"])},
        success_url=(
            f"{base_url}/order-confirmation?conf={order['confirmation_number']}"
            "&session_id={CHECKOUT_SESSION_ID}"
        ),
        cancel_url=f"{base_url}/checkout?canceled=1",
    )

    set_order_stripe_session(order["id"], checkout_session.id)
    return checkout_session.url


def confirm_paid_session(checkout_session):
    """
    Marks the order PAID if Stripe says this Checkout Session is paid and it matches the order.
    checkout_session is a plain dict. Returns the order (None if no order matches).
    """
    order_id = (checkout_session.get("metadata") or {}).get("order_id")
    if not order_id:
        logger.warning("[stripe] session %s has no order_id", checkout_session.get("id"))
        return None

    order = get_order_by_id(int(order_id))
    if not order:
        logger.warning("[stripe] session %s points at missing order %s", checkout_session.get("id"), order_id)
        return None

    if checkout_session.get("payment_status") != "paid":
        return order

    # The session must be the one we created for this order, for the full amount
    if checkout_session.get("id") != order["stripe_session_id"]:
        logger.warning("[stripe] session %s does not match order %s", checkout_session.get("id"), order["id"])
        return order
    if checkout_session.get("amount_total") != to_cents(order["total_amount"]):
        logger.warning("[stripe] amount mismatch on order %s", order["id"])
        return order

    # mark_order_paid only returns True once, so fulfillment never runs twice
    if mark_order_paid(order["id"]):
        fulfill_paid_order(order)
        order["order_status"] = "PAID"

    return order


def handle_stripe_webhook(payload, signature_header):
    """
    Checks the webhook really came from Stripe, then confirms paid sessions.
    Raises ValueError or stripe.SignatureVerificationError for bad requests.
    """
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise PaymentConfigError("Add STRIPE_WEBHOOK_SECRET to your .env file.")

    event = stripe.Webhook.construct_event(payload, signature_header, secret)

    if event.type in PAID_EVENT_TYPES:
        confirm_paid_session(event.data.object.to_dict())

    return event.type


def confirm_session_for_user(session_id, user_id):
    """Asks Stripe for the session when the buyer comes back from paying, so the page doesn't wait on the webhook."""
    _use_secret_key()
    checkout_session = stripe.checkout.Session.retrieve(session_id)
    order = confirm_paid_session(checkout_session.to_dict())
    if not order or order["user_id"] != user_id:
        raise Exception("Order not found.")
    return order
