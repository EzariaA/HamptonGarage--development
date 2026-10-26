# The Vault Campus Marketplace
# CSC 405 Sp 26'
# Updated by Day Ekoi - 4/22/26 - API-only blueprint
# Updated by Mattie Edozie - 10/26/26 - checkout now goes through Stripe; orders are PAID only after Stripe confirms

import logging
import os

import stripe
from flask import Blueprint, request, jsonify, session

from services.checkout_service import (
    create_pending_order,
    get_order_summary_service,
    get_user_orders_service,
)
from services.payment_service import (
    PaymentConfigError,
    confirm_session_for_user,
    handle_stripe_webhook,
    payments_configured,
    start_stripe_checkout,
)

logger = logging.getLogger(__name__)

checkout_bp = Blueprint("checkout", __name__)


def _base_url():
    """Where Stripe sends the buyer back to. APP_BASE_URL wins if it's set."""
    return (os.getenv("APP_BASE_URL") or request.host_url).rstrip("/")


# Saves the order as PENDING_PAYMENT and sends back the Stripe payment page URL
@checkout_bp.route("/checkout/complete", methods=["POST"])
def complete_checkout():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    session_cart = session.get("cart", [])
    if not session_cart:
        return jsonify({"error": "Cart is empty"}), 400

    # Check before saving anything so we don't leave unpaid orders behind
    if not payments_configured():
        return jsonify({"error": "Online payments are not set up yet. Please try again later."}), 503

    data = request.get_json() or {}

    try:
        result = create_pending_order(user_id, session_cart, data)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    try:
        checkout_url = start_stripe_checkout(result["order"], result["order_items"], _base_url())
    except (PaymentConfigError, stripe.StripeError) as e:
        logger.warning("[stripe] could not start checkout for order %s: %s", result["order"]["id"], e)
        return jsonify({"error": "Could not reach the payment service. Please try again."}), 502

    return jsonify({
        "success": True,
        "checkout_url": checkout_url,
        "confirmation_number": result["confirmation_number"],
        "order_id": result["order"]["id"],
        "total_amount": result["total_amount"],
    }), 200


# Stripe calls this after a payment. It is the main way an order becomes PAID.
@checkout_bp.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    try:
        event_type = handle_stripe_webhook(request.get_data(), request.headers.get("Stripe-Signature", ""))
    except PaymentConfigError as e:
        logger.error("[stripe] webhook received but %s", e)
        return jsonify({"error": "Webhook not configured"}), 500
    except (ValueError, stripe.SignatureVerificationError):
        return jsonify({"error": "Invalid signature"}), 400

    return jsonify({"received": event_type}), 200


# The confirmation page calls this when the buyer comes back from Stripe
@checkout_bp.route("/checkout/confirm", methods=["GET"])
def confirm_checkout():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    session_id = request.args.get("session_id", "")
    if not session_id:
        return jsonify({"error": "Missing session_id"}), 400

    try:
        order = confirm_session_for_user(session_id, user_id)
    except stripe.StripeError as e:
        logger.warning("[stripe] could not check session %s: %s", session_id, e)
        return jsonify({"error": "Could not reach the payment service."}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 400

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
