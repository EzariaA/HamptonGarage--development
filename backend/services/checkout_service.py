# The Vault Campus Marketplace
# CSC 405 Sp 26'
# Updated by Day Ekoi - 4/22/26
import logging  # added - ava
logger = logging.getLogger(__name__)  # added - ava
import random
import string
from datetime import datetime

from models.checkout_model import (
    create_order,
    create_order_item,
    get_order_by_confirmation,
    get_order_items_by_order_id,
    get_orders_by_user_id,
    clear_cart_for_user,
    update_listing_size_inventory,
    remove_purchased_from_wishlist,
    check_listing_availability,
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
    """
    if not session_cart:
        raise Exception("Cart is empty.")

    # Validate all cart items are still available before creating the order.
    # Each price comes from the listings table, not the session cart, so the order
    # total matches what Stripe charged (Stripe is also given the database price).
    # Updated by Ava Bell - Iteration 3 - 10/27/26 (HG-100)
    db_prices = {}
    for item in session_cart:
        item_id = item.get("id")
        quantity = int(item.get("quantity", 1))
        if not item_id:
            raise Exception("An item in your cart is no longer available.")
        check_listing_availability(int(item_id), quantity)
        listing = get_listing_by_id(int(item_id))
        if not listing:
            raise Exception("An item in your cart is no longer available.")
        db_prices[int(item_id)] = round(float(listing["price"]), 2)

    first_name = (buyer_details.get("first_name") or "").strip()
    last_name = (buyer_details.get("last_name") or "").strip()
    email = (buyer_details.get("email") or "").strip()
    contact = (buyer_details.get("contact") or "").strip()
    meeting_location = (buyer_details.get("meeting_location") or "").strip()

    if not all([first_name, last_name, email, contact, meeting_location]):
        raise Exception("All buyer details are required.")

    total_amount = round(
        sum(db_prices[int(item["id"])] * int(item.get("quantity", 1)) for item in session_cart),
        2,
    )

    confirmation_number = _generate_confirmation_number()

    order = create_order(
        user_id=user_id,
        confirmation_number=confirmation_number,
        buyer_first_name=first_name,
        buyer_last_name=last_name,
        buyer_email=email,
        buyer_contact=contact,
        buyer_meeting_location=meeting_location,
        total_amount=total_amount,
        order_status="PENDING_PAYMENT",  # not paid yet
    )

    order_items = []
    for item in session_cart:
        order_item = create_order_item(
            order_id=order["id"],
            listing_id=item.get("id"),
            item_name=item.get("name", "Item"),
            quantity=int(item.get("quantity", 1)),
            price_at_purchase=db_prices[int(item["id"])],
            selected_size=item.get("size"),
        )
        order_items.append(order_item)

    return {
        "confirmation_number": confirmation_number,
        "order": order,
        "order_items": order_items,
        "total_amount": total_amount,
    }


def get_order_summary_service(confirmation_number, user_id):
    """Returns order + items for the confirmation page. Validates user ownership."""
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
