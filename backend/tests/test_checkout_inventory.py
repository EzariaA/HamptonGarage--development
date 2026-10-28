# backend/tests/test_checkout_inventory.py
# Created by Kyle Lewis 10/26/26 - Iteration 3 (K1)
# Tests that checkout lowers the stock and blocks sold out items (Test IDs K1-1 and K1-2)

from db import get_connection
from models.checkout_model import InventoryError
from services.checkout_service import complete_transaction_from_session

import pytest


# makes one cart item the same way the session cart stores it
def cart_item(listing, quantity=1, size=None):
    return {"id": listing["id"], "name": listing["title"], "price": listing["price"],
            "quantity": quantity, "size": size}


def count_orders():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM orders;")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count


# K1-1: completing an order (after Stripe says it's paid) lowers the size stock and the total stock
def test_checkout_lowers_stock(make_user, make_listing, get_listing, buyer_details):
    listing = make_listing(quantity=5, sizes={"S": 2, "M": 3})
    buyer = make_user("buyer")

    complete_transaction_from_session(buyer["id"], [cart_item(listing, quantity=2, size="M")], buyer_details)

    after = get_listing(listing["id"])
    assert after["quantity_on_hand"] == 3
    assert after["sizes"] == {"S": 2, "M": 1}
    assert after["status"] == "ACTIVE"
    assert count_orders() == 1


# K1-2: a sold out item can't be checked out, no order is made, and the stock doesn't change
def test_sold_out_item_blocks_checkout(make_user, make_listing, get_listing, buyer_details):
    listing = make_listing(quantity=0, status="SOLD_OUT")
    buyer = make_user("buyer")

    with pytest.raises(InventoryError) as error:
        complete_transaction_from_session(buyer["id"], [cart_item(listing)], buyer_details)

    assert "sold out" in str(error.value)
    assert count_orders() == 0
    assert get_listing(listing["id"])["quantity_on_hand"] == 0
