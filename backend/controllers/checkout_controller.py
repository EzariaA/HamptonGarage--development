# Hampton Garage 
# Updated by Ezaria Alexnader
#How checkout works:
#   1. checkout.js sends the buyer's details to /api/checkout/create-session
#   2. We check stock and prices (from the database), then ask Stripe for a payment page
#   3. The buyer pays on Stripe's page (we never see the card)
#   4. Stripe sends the buyer to /api/checkout/success; we confirm with Stripe that it was paid, and only then create the order, update stock, and empty the cart

import logging
import os
import stripe
from flask import Blueprint, request, jsonify, session, redirect

from db import get_connection
from models.listing_model import get_listing_by_id
from models.checkout_model import check_listing_availability, InventoryError
from services.checkout_service import (
    complete_transaction_from_session,
    get_order_summary_service,
    get_user_orders_service,
    validate_card,
)
from services.payment_service import (
    check_payment_on_return,
    handle_stripe_webhook,
    payments_configured,
    start_stripe_checkout,
)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
REQUIRED_FIELDS = ["first_name", "last_name", "email", "contact", "meeting_location"]

logger = logging.getLogger(__name__)
checkout_bp = Blueprint("checkout", __name__)


# Checks the mock card info, then places the order or sends back the card errors
# Updated by Mason Johnson - Iteration 2 - 10/26/26 - added mock card check before placing the order
@checkout_bp.route("/checkout/complete", methods=["POST"])
def complete_checkout():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    session_cart = session.get("cart", [])
    if not session_cart:
        return jsonify({"error": "Cart is empty"}), 400

    data = request.get_json() or {}

    # Mock payment: check the card fields. Card data is not passed on or saved anywhere.
    card_errors = validate_card(data.get("card") or {})
    if card_errors:
        return jsonify({
            "error": "Please fix the card details below.",
            "card_errors": card_errors,
        }), 400

    try:
        result = complete_transaction_from_session(user_id, session_cart, data)
        session["cart"] = []
        session.modified = True
        return jsonify({
            "success": True,
            "confirmation_number": result["confirmation_number"],
            "order_id": result["order"]["id"],
            "total_amount": result["total_amount"],
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

checkout_bp = Blueprint("checkout", __name__)

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
    
@checkout_bp.route("/checkout/create-session", methods=["POST"])
def create_checkout_session():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401
    cart = session.get("cart", [])
    if not cart:
        return jsonify({"error": "Cart is empty"}), 400

    data = request.get_json() or {}
    buyer = {f: (data.get(f) or "").strip() for f in REQUIRED_FIELDS}
    if not all(buyer.values()):
        return jsonify({"error": "Please fill in all fields."}), 400

    try:
        line_items = []
        for item in cart:
            listing_id = int(item["id"])
            qty = int(item.get("quantity", 1))
            check_listing_availability(listing_id, qty)
            listing = get_listing_by_id(listing_id)
            if not listing:
                return jsonify({"error": "An item in your cart is no longer available."}), 400
            line_items.append({
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": item.get("name") or "Item"},
                    "unit_amount": int(round(float(listing["price"]) * 100)),
                },
                "quantity": qty,
            })

        stripe_session = stripe.checkout.Session.create(
            mode="payment",
            line_items=line_items,
            customer_email=buyer["email"],
            success_url=request.host_url + "api/checkout/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.host_url + "checkout?status=cancelled",
            metadata={"user_id": str(user_id)},
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    session["pending_buyer"] = buyer
    return jsonify({"url": stripe_session.url})


@checkout_bp.route("/checkout/success")
def checkout_success():
    session_id = request.args.get("session_id")
    user_id = session.get("user_id")
    if not session_id or not user_id:
        return redirect("/checkout")

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT confirmation_number FROM orders WHERE stripe_session_id = %s", (session_id,))
        row = cur.fetchone()
        if row:
            return redirect(f"/order-confirmation?conf={row[0]}")

        stripe_session = stripe.checkout.Session.retrieve(session_id)
        if stripe_session.payment_status != "paid" or stripe_session.metadata.to_dict().get("user_id") != str(user_id):            return redirect("/checkout")

        buyer = session.pop("pending_buyer", {})
        try:
            result = complete_transaction_from_session(user_id, session.get("cart", []), buyer)
        except InventoryError:
            try:
                stripe.Refund.create(payment_intent=stripe_session.payment_intent)
            except stripe.StripeError:
                pass  # already refunded (the buyer refreshed this page)
            return redirect("/checkout?error=sold_out")
        except Exception:
            # The buyer has paid, but the order could not be created (for example, an item
            # sold out in between). Log it, keep the cart, and send the buyer back with the
            # Stripe session ID as a reference.
            logger.error(
                "Paid but no order created: user_id=%s stripe_session_id=%s",
                user_id, session_id, exc_info=True,
            )
            return redirect(f"/checkout?status=order_failed&ref={session_id}")
        cur.execute(
            "UPDATE orders SET stripe_session_id = %s, payment_status = 'paid' WHERE confirmation_number = %s",
            (session_id, result["confirmation_number"]),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    session["cart"] = []
    session.modified = True
    return redirect(f"/order-confirmation?conf={result['confirmation_number']}")