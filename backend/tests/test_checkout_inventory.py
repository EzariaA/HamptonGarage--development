# backend/tests/test_checkout_inventory.py
# Created by Kyle Lewis 10/26/26 - Iteration 3 (K1)
# Tests that checkout lowers the stock and blocks sold out items (Test IDs K1-1 and K1-2)

from db import get_connection


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


def checkout(client, buyer_details):
    return client.post("/api/checkout/complete", json=buyer_details)


# K1-1: buying 2 of size M lowers the size stock and the total stock
def test_checkout_lowers_stock(client, make_user, make_listing, login_as, get_listing, buyer_details):
    listing = make_listing(quantity=5, sizes={"S": 2, "M": 3})
    login_as(make_user("buyer"), cart=[cart_item(listing, quantity=2, size="M")])

    response = checkout(client, buyer_details)
    assert response.status_code == 200

    after = get_listing(listing["id"])
    assert after["quantity_on_hand"] == 3
    assert after["sizes"] == {"S": 2, "M": 1}
    assert after["status"] == "ACTIVE"
    assert count_orders() == 1

# K1-2: a sold out item can't be checked out, no order is made, and the cart is not erased
def test_sold_out_item_blocks_checkout(client, make_user, make_listing, login_as, buyer_details):
    listing = make_listing(quantity=0, status="SOLD_OUT")
    login_as(make_user("buyer"), cart=[cart_item(listing)])

    response = checkout(client, buyer_details)
    assert response.status_code == 400
    assert "sold out" in response.get_json()["error"]
    assert count_orders() == 0

    with client.session_transaction() as session:
        assert len(session["cart"]) == 1
