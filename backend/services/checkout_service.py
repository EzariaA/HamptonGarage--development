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


# ________________________________________________________
# MOCK CARD PAYMENT CHECKS
# Added by Mason Johnson - Iteration 2 - 10/26/26
# No real payment service is used. The full card number and CVV
# are only checked here and are never saved or logged.
# ________________________________________________________

def is_all_digits(text):
    """Returns True if the text is not empty and every character is 0-9."""
    if text == "":
        return False
    for char in text:
        if char not in "0123456789":
            return False
    return True


def passes_luhn_check(card_number):
    """
    Runs the Luhn check on a string of digits.
    Starting from the right, every second digit is doubled
    (subtract 9 if it goes over 9). The total must end in 0.
    """
    total = 0
    reversed_number = card_number[::-1]

    for i in range(len(reversed_number)):
        digit = int(reversed_number[i])
        if i % 2 == 1:
            digit = digit * 2
            if digit > 9:
                digit = digit - 9
        total = total + digit

    return total % 10 == 0


def validate_card(card):
    """
    Checks the mock card form fields.
    Returns a dictionary of field name -> error message.
    An empty dictionary means the card is valid.
    """
    errors = {}

    name = (card.get("name") or "").strip()
    number = (card.get("number") or "").replace(" ", "").replace("-", "")
    expiry = (card.get("expiry") or "").strip()
    cvv = (card.get("cvv") or "").strip()

    # Cardholder name
    if not name:
        errors["name"] = "Enter the name on the card."

    # Card number: 13 to 19 digits and must pass the Luhn check
    if not number:
        errors["number"] = "Enter a card number."
    elif not is_all_digits(number):
        errors["number"] = "Card number can only contain digits."
    elif len(number) < 13 or len(number) > 19:
        errors["number"] = "Card number must be 13 to 19 digits."
    elif not passes_luhn_check(number):
        errors["number"] = "This card number is not valid. Please check it and try again."

    # Expiration date: MM/YY and not in the past
    if not expiry:
        errors["expiry"] = "Enter the expiration date."
    elif len(expiry) != 5 or expiry[2] != "/" or not is_all_digits(expiry[:2]) or not is_all_digits(expiry[3:]):
        errors["expiry"] = "Use the format MM/YY."
    else:
        month = int(expiry[:2])
        year = 2000 + int(expiry[3:])
        today = datetime.now()

        if month < 1 or month > 12:
            errors["expiry"] = "Month must be between 01 and 12."
        elif year < today.year or (year == today.year and month < today.month):
            errors["expiry"] = "This card has expired."

    # CVV: 3 or 4 digits
    if not cvv:
        errors["cvv"] = "Enter the CVV."
    elif not is_all_digits(cvv) or len(cvv) < 3 or len(cvv) > 4:
        errors["cvv"] = "CVV must be 3 or 4 digits."

    return errors


def complete_transaction_from_session(user_id, session_cart, buyer_details):
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
        order_status="PENDING_PAYMENT",  # not paid yet
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
    """
    Takes the bought items out of stock and empties the buyer's cart and wishlist.
    Only call this after the order is PAID (payment_service.py does this).
    """
    order_items = get_order_items_by_order_id(order["id"])

    # Take each item out of stock
    for item in order_items:
        item_id = item.get("listing_id")
        size = item.get("selected_size")
        if item_id and size:
            try:
                update_listing_size_inventory(int(item_id), size, int(item["quantity"]))
            except Exception as e:
                logger.warning(f"[checkout] inventory update failed for listing {item_id} size {size}: {e}")

    # Empty the buyer's saved cart
    clear_cart_for_user(order["user_id"])

    # Remove the bought items from the buyer's wishlist
    purchased_listing_ids = []
    for item in order_items:
        if item.get("listing_id") is not None:
            purchased_listing_ids.append(item["listing_id"])
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
