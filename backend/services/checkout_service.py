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


def _generate_confirmation_number():
    date_str = datetime.now().strftime("%y%m%d")
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"VAULT-{date_str}-{suffix}"


# Updated by Mattie Edozie - 10/26/26 - split into create_pending_order + fulfill_paid_order.
# The order is saved as PENDING_PAYMENT here. Inventory, cart and wishlist only change
# in fulfill_paid_order, which runs after Stripe confirms the payment.
def create_pending_order(user_id, session_cart, buyer_details):
    """
    Saves the order and its items as PENDING_PAYMENT using the session cart and buyer details.

    buyer_details keys: first_name, last_name, email, contact, meeting_location
    session_cart items: { id, name, price, quantity, size }
    """
    if not session_cart:
        raise Exception("Cart is empty.")

    # Validate all cart items are still available before creating the order
    for item in session_cart:
        item_id = item.get("id")
        quantity = int(item.get("quantity", 1))
        if item_id:
            check_listing_availability(int(item_id), quantity)

    first_name = (buyer_details.get("first_name") or "").strip()
    last_name = (buyer_details.get("last_name") or "").strip()
    email = (buyer_details.get("email") or "").strip()
    contact = (buyer_details.get("contact") or "").strip()
    meeting_location = (buyer_details.get("meeting_location") or "").strip()

    if not all([first_name, last_name, email, contact, meeting_location]):
        raise Exception("All buyer details are required.")

    total_amount = round(
        sum(float(item.get("price", 0)) * int(item.get("quantity", 1)) for item in session_cart),
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
        order_status="PENDING_PAYMENT",
    )

    order_items = []
    for item in session_cart:
        order_item = create_order_item(
            order_id=order["id"],
            listing_id=item.get("id"),
            item_name=item.get("name", "Item"),
            quantity=int(item.get("quantity", 1)),
            price_at_purchase=float(item.get("price", 0)),
            selected_size=item.get("size"),
        )
        order_items.append(order_item)

    return {
        "confirmation_number": confirmation_number,
        "order": order,
        "order_items": order_items,
        "total_amount": total_amount,
    }


def fulfill_paid_order(order):
    """Updates inventory, clears the buyer's cart and wishlist. Call only after the order is PAID."""
    order_items = get_order_items_by_order_id(order["id"])

    for item in order_items:
        item_id = item.get("listing_id")
        size = item.get("selected_size")
        if item_id and size:
            try:
                update_listing_size_inventory(int(item_id), size, int(item["quantity"]))
            except Exception as e:
                logger.warning(f"[checkout] inventory update failed for listing {item_id} size {size}: {e}")

    clear_cart_for_user(order["user_id"])

    # Remove purchased listings from the user's wishlist
    purchased_listing_ids = [item.get("listing_id") for item in order_items if item.get("listing_id") is not None]
    try:
        remove_purchased_from_wishlist(order["user_id"], purchased_listing_ids)
    except Exception as e:
        logger.warning(f"[checkout] wishlist cleanup failed: {e}")


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
