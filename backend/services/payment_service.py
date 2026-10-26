# The Vault Campus Marketplace
# CSC 404 Fall 26'
# Created by Mattie Edozie - 10/26/26
#
# STRIPE PAYMENTS
# Stripe is the company that actually charges the buyer's card.
# How it works:
#   1. We save the order as PENDING_PAYMENT (not paid yet).
#   2. We ask Stripe to make a payment page for that order (a "Checkout Session").
#   3. The buyer types their card on STRIPE'S page, not ours. We never see the card number.
#   4. Stripe tells us the payment went through. ONLY THEN do we mark the order PAID.
#
# Stripe tells us in two ways (whichever happens first wins, the other does nothing):
#   - Webhook: Stripe's server sends a message to our /api/stripe/webhook route.
#   - Return page: when the buyer comes back to our site, we ask Stripe "did they pay?"
import logging
import os

import stripe

from models.checkout_model import get_order_by_id, mark_order_paid, set_order_stripe_session
from services.checkout_service import fulfill_paid_order

logger = logging.getLogger(__name__)


def payments_configured():
    """Returns True if the Stripe secret key is set in .env (or in the AWS settings)."""
    return bool(os.getenv("STRIPE_SECRET_KEY"))


def dollars_to_cents(amount):
    """Stripe wants prices in cents, not dollars. Example: 12.50 -> 1250"""
    return int(round(float(amount) * 100))


def start_stripe_checkout(order, order_items, base_url):
    """
    Asks Stripe to make a payment page for this order.
    Returns the link to that page so we can send the buyer there.
    """
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

    # Build the list of items Stripe shows on its payment page
    line_items = []
    for item in order_items:
        name = item["item_name"]
        if item["selected_size"]:
            name = name + " (Size " + item["selected_size"] + ")"

        line_items.append({
            "price_data": {
                "currency": "usd",
                "product_data": {"name": name},
                "unit_amount": dollars_to_cents(item["price_at_purchase"]),
            },
            "quantity": item["quantity"],
        })

    # Where Stripe sends the buyer after paying, or after hitting "back".
    # Stripe replaces {CHECKOUT_SESSION_ID} with the real session id for us.
    success_url = base_url + "/order-confirmation?conf=" + order["confirmation_number"] + "&session_id={CHECKOUT_SESSION_ID}"
    cancel_url = base_url + "/checkout?canceled=1"

    stripe_session = stripe.checkout.Session.create(
        mode="payment",
        line_items=line_items,
        customer_email=order["buyer_email"],
        metadata={"order_id": str(order["id"])},  # so we know which order this payment is for
        success_url=success_url,
        cancel_url=cancel_url,
    )

    # Save Stripe's session id on the order so we can match them up later
    set_order_stripe_session(order["id"], stripe_session.id)

    return stripe_session.url


def mark_paid_if_stripe_confirms(stripe_session):
    """
    Looks at what Stripe told us about a payment.
    If everything checks out, marks the order PAID.
    stripe_session is a normal Python dictionary.
    Returns the order, or None if we can't find it.
    """
    # Which order is this payment for? We put the order id in "metadata" when we made the session.
    metadata = stripe_session.get("metadata") or {}
    order_id = metadata.get("order_id")
    if not order_id:
        logger.warning("[stripe] payment has no order_id")
        return None

    order = get_order_by_id(int(order_id))
    if not order:
        logger.warning("[stripe] payment is for an order that doesn't exist: %s", order_id)
        return None

    # Check 1: did Stripe actually take the money?
    if stripe_session.get("payment_status") != "paid":
        return order

    # Check 2: is this the payment page we made for THIS order?
    if stripe_session.get("id") != order["stripe_session_id"]:
        logger.warning("[stripe] payment doesn't match order %s", order_id)
        return order

    # Check 3: did they pay the full price?
    if stripe_session.get("amount_total") != dollars_to_cents(order["total_amount"]):
        logger.warning("[stripe] wrong amount paid for order %s", order_id)
        return order

    # All checks passed. mark_order_paid returns True only the FIRST time,
    # so if Stripe tells us twice, we don't take the items out of stock twice.
    if mark_order_paid(order["id"]):
        fulfill_paid_order(order)
        order["order_status"] = "PAID"

    return order


def handle_stripe_webhook(payload, signature):
    """
    Runs when Stripe's server sends us a message (a "webhook").
    construct_event checks the message's signature, which proves it really came
    from Stripe and not from someone pretending. A fake message raises an error.
    """
    event = stripe.Webhook.construct_event(payload, signature, os.getenv("STRIPE_WEBHOOK_SECRET"))

    # We only care about "the buyer finished paying" messages
    if event.type == "checkout.session.completed" or event.type == "checkout.session.async_payment_succeeded":
        # to_dict() turns Stripe's object into a normal Python dictionary
        mark_paid_if_stripe_confirms(event.data.object.to_dict())

    return event.type


def check_payment_on_return(session_id, user_id):
    """
    Runs when the buyer lands back on our site after paying.
    We ask Stripe directly about the payment so the buyer sees PAID right away,
    without waiting for the webhook.
    """
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    stripe_session = stripe.checkout.Session.retrieve(session_id)

    order = mark_paid_if_stripe_confirms(stripe_session.to_dict())

    # Don't let someone look up another person's order
    if not order or order["user_id"] != user_id:
        raise Exception("Order not found.")

    return order
