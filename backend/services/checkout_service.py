# The Vault Campus Marketplace
# CSC 405 Sp 26'
# Updated by Day Ekoi - 4/22/26
import logging  # added - ava
logger = logging.getLogger(__name__)  # added - ava
import random
import string
from datetime import datetime

from models.checkout_model import (
    place_order_with_inventory,
    get_order_by_confirmation,
    get_order_items_by_order_id,
    get_orders_by_user_id,
    clear_cart_for_user,
    remove_purchased_from_wishlist,
)
from models.listing_model import get_listing_by_id


def _generate_confirmation_number():
    date_str = datetime.now().strftime("%y%m%d")
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"VAULT-{date_str}-{suffix}"


def complete_transaction_from_session(user_id, session_cart, buyer_details):
    """
    Saves the order and its items as PENDING_PAYMENT using the session cart and buyer details.

    buyer_details keys: first_name, last_name, email, contact, meeting_location
    session_cart items: { id, name, price, quantity, size }

    Kyle Lewis (K1) - the order and the stock change are now saved
    together in place_order_with_inventory(). If something is sold out it raises
    InventoryError and no order is made.

    Ava Bell (HG-100) - each price comes from the listings table, not the session
    cart, so the order total matches what Stripe charged (Stripe is also given the
    database price). The price in the session cart is ignored.
    """
    if not session_cart:
        raise Exception("Cart is empty.")

    first_name = (buyer_details.get("first_name") or "").strip()
    last_name = (buyer_details.get("last_name") or "").strip()
    email = (buyer_details.get("email") or "").strip()
    contact = (buyer_details.get("contact") or "").strip()
    meeting_location = (buyer_details.get("meeting_location") or "").strip()

    if not all([first_name, last_name, email, contact, meeting_location]):
        raise Exception("All buyer details are required.")

    cart_items = []
    for item in session_cart:
        quantity = int(item.get("quantity", 1))
        if quantity <= 0:
            raise Exception("Item quantities must be at least 1.")
        item_id = item.get("id")
        if item_id in (None, ""):
            raise Exception("An item in your cart is no longer available.")
        listing = get_listing_by_id(int(item_id))
        if not listing:
            raise Exception("An item in your cart is no longer available.")
        cart_items.append({
            "listing_id": int(item_id),
            "item_name": item.get("name", "Item"),
            "quantity": quantity,
            "price": round(float(listing["price"]), 2),  # database price (HG-100)
            "size": item.get("size") or None,
        })

    total_amount = round(sum(i["price"] * i["quantity"] for i in cart_items), 2)
    confirmation_number = _generate_confirmation_number()

    result = place_order_with_inventory(
        user_id=user_id,
        confirmation_number=confirmation_number,
        buyer={
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "contact": contact,
            "meeting_location": meeting_location,
        },
        cart_items=cart_items,
        total_amount=total_amount,
        order_status="PENDING_PAYMENT",  # not paid yet
    )

    clear_cart_for_user(user_id)

    # Remove purchased listings from the user's wishlist
    purchased_listing_ids = [i["listing_id"] for i in cart_items if i["listing_id"] is not None]
    try:
        remove_purchased_from_wishlist(user_id, purchased_listing_ids)
    except Exception as e:
        logger.warning(f"[checkout] wishlist cleanup failed: {e}")

    return {
        "confirmation_number": confirmation_number,
        "order": result["order"],
        "order_items": result["order_items"],
        "total_amount": total_amount,
    }


def get_order_summary_service(confirmation_number, user_id):
    """Returns order + items for the confirmation page. Validatesuser ownership."""
    order = get_order_by_confirmation(confirmation_number)
    if not order:
        raise Exception("Order not found.")
    if order["user_id"] != user_id:
        raise Exception("Access denied.")
    items = get_order_items_by_order_id(order["id"])
    return {"order": order, "order_items": items}


def get_user_orders_service(user_id):
    """Returns all orders for the given user, newest first."""
    return get_orders_by_user_id(user_id)
