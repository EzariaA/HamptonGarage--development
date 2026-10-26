# The Vault Campus Marketplace
# CSC 405 Sp 26'
# Updated by Day Ekoi - 4/22/26 - API-only blueprint
# Updated by Mattie Edozie - 10/26/26 - checkout now goes through Stripe.
#   Orders are only marked PAID after Stripe confirms. See services/payment_service.py
#   and docs/edozie-changes.md for how it works.

import logging
import os

from flask import Blueprint, request, jsonify, session

from services.checkout_service import (
    create_pending_order,
    get_order_summary_service,
    get_user_orders_service,
)
from services.payment_service import (
    check_payment_on_return,
    handle_stripe_webhook,
    payments_configured,
    start_stripe_checkout,
)

logger = logging.getLogger(__name__)

checkout_bp = Blueprint("checkout", __name__)


# Step 1 of checkout: the buyer clicks "Continue to Payment".
# We save the order as PENDING_PAYMENT and send back the link to Stripe's payment page.
# Updated by Mattie Edozie - 10/26/26
@checkout_bp.route("/checkout/complete", methods=["POST"])
def complete_checkout():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    session_cart = session.get("cart", [])
    if not session_cart:
        return jsonify({"error": "Cart is empty"}), 400

    # If Stripe isn't set up, stop here so we don't save an order nobody can pay for
    if not payments_configured():
        return jsonify({"error": "Online payments are not set up yet. Please try again later."}), 503

    data = request.get_json() or {}

    # Save the order (not paid yet)
    try:
        result = create_pending_order(user_id, session_cart, data)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    # Ask Stripe for a payment page
    try:
        # request.host_url is our site's address, like http://127.0.0.1:5000/
        checkout_url = start_stripe_checkout(result["order"], result["order_items"], request.host_url.rstrip("/"))
    except Exception as e:
        logger.warning("[stripe] could not start checkout: %s", e)
        return jsonify({"error": "Could not reach the payment service. Please try again."}), 502

    # The cart is NOT emptied yet. That only happens once the order is paid.
    return jsonify({
        "success": True,
        "checkout_url": checkout_url,
        "confirmation_number": result["confirmation_number"],
    }), 200


# Stripe's server calls this route when a payment goes through (this is the "webhook").
# This is the main way an order becomes PAID.
# Added by Mattie Edozie - 10/26/26
@checkout_bp.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    if not os.getenv("STRIPE_WEBHOOK_SECRET"):
        logger.error("[stripe] webhook received but STRIPE_WEBHOOK_SECRET is not set")
        return jsonify({"error": "Webhook not set up"}), 500

    try:
        # get_data() is the raw message. The signature header proves Stripe sent it.
        event_type = handle_stripe_webhook(request.get_data(), request.headers.get("Stripe-Signature", ""))
    except Exception:
        # The signature didn't match, so this message did not come from Stripe
        return jsonify({"error": "Invalid signature"}), 400

    return jsonify({"received": event_type}), 200


# The order confirmation page calls this when the buyer comes back from Stripe.
# We ask Stripe if they paid, and mark the order PAID if they did.
# Added by Mattie Edozie - 10/26/26
@checkout_bp.route("/checkout/confirm", methods=["GET"])
def confirm_checkout():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    session_id = request.args.get("session_id", "")
    if not session_id:
        return jsonify({"error": "Missing session_id"}), 400

    try:
        order = check_payment_on_return(session_id, user_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    # Paid, so now it's safe to empty the buyer's cart
    if order["order_status"] == "PAID":
        session["cart"] = []
        session.modified = True

    return jsonify({
        "confirmation_number": order["confirmation_number"],
        "order_status": order["order_status"],
    }), 200


@checkout_bp.route("/orders/by-confirmation/<confirmation_number>", methods=["GET"])
def get_order_confirmation(confirmation_number):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    try:
        result = get_order_summary_service(confirmation_number, user_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@checkout_bp.route("/orders/my", methods=["GET"])
def get_my_orders():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    try:
        orders = get_user_orders_service(user_id)
        return jsonify({"orders": orders}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
