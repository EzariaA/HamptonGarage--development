# backend/tests/test_checkout_inventory.py
# Created by Kyle Lewis 10/26/26 - Iteration 3 (K1)
# Tests that checkout lowers the stock and blocks sold out items (Test IDs K1-1 to K1-10)

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


# K1-2: buying the last one makes the listing SOLD_OUT
def test_buying_last_item_makes_it_sold_out(client, make_user, make_listing, login_as, get_listing, buyer_details):
    listing = make_listing(quantity=1, sizes={"L": 1})
    login_as(make_user("buyer"), cart=[cart_item(listing, quantity=1, size="L")])

    response = checkout(client, buyer_details)
    assert response.status_code == 200

    after = get_listing(listing["id"])
    assert after["quantity_on_hand"] == 0
    assert after["status"] == "SOLD_OUT"


# K1-3: a sold out item can't be checked out, no order is made, and the cart is not erased
def test_sold_out_item_blocks_checkout(client, make_user, make_listing, login_as, buyer_details):
    listing = make_listing(quantity=0, status="SOLD_OUT")
    login_as(make_user("buyer"), cart=[cart_item(listing)])

    response = checkout(client, buyer_details)
    assert response.status_code == 400
    assert "sold out" in response.get_json()["error"]
    assert count_orders() == 0

    with client.session_transaction() as session:
        assert len(session["cart"]) == 1


# K1-4: asking for more than what's in stock is blocked and the stock doesn't change
def test_more_than_in_stock_blocks_checkout(client, make_user, make_listing, login_as, get_listing, buyer_details):
    listing = make_listing(quantity=2)
    login_as(make_user("buyer"), cart=[cart_item(listing, quantity=3)])

    response = checkout(client, buyer_details)
    assert response.status_code == 400
    assert "only has 2" in response.get_json()["error"]
    assert get_listing(listing["id"])["quantity_on_hand"] == 2
    assert count_orders() == 0


# K1-5: a size that is sold out is blocked even if other sizes are in stock
def test_sold_out_size_blocks_checkout(client, make_user, make_listing, login_as, get_listing, buyer_details):
    listing = make_listing(quantity=2, sizes={"S": 0, "M": 2})
    login_as(make_user("buyer"), cart=[cart_item(listing, quantity=1, size="S")])

    response = checkout(client, buyer_details)
    assert response.status_code == 400
    assert "size S" in response.get_json()["error"]
    assert get_listing(listing["id"])["sizes"] == {"S": 0, "M": 2}


# K1-6: two cart lines of the same item get added together (1 + 1 is more than the 1 in stock)
def test_same_item_twice_in_cart_is_counted_together(client, make_user, make_listing, login_as, get_listing, buyer_details):
    listing = make_listing(quantity=1)
    login_as(make_user("buyer"), cart=[cart_item(listing), cart_item(listing)])

    response = checkout(client, buyer_details)
    assert response.status_code == 400
    assert get_listing(listing["id"])["quantity_on_hand"] == 1
    assert count_orders() == 0


# K1-7: if one item is sold out, the whole order is cancelled and the other item's stock isn't touched
def test_one_sold_out_item_cancels_whole_order(client, make_user, make_listing, login_as, get_listing, buyer_details):
    in_stock = make_listing(title="In Stock Tee", quantity=4)
    sold_out = make_listing(title="Sold Out Tee", quantity=0, status="SOLD_OUT")
    login_as(make_user("buyer"), cart=[cart_item(in_stock), cart_item(sold_out)])

    response = checkout(client, buyer_details)
    assert response.status_code == 400
    assert get_listing(in_stock["id"])["quantity_on_hand"] == 4
    assert count_orders() == 0


# K1-8: made to order items can be bought with no stock and are never marked sold out
def test_made_to_order_items_are_not_lowered(client, make_user, make_listing, login_as, get_listing, buyer_details):
    listing = make_listing(quantity=0, made_to_order=True)
    login_as(make_user("buyer"), cart=[cart_item(listing, quantity=3)])

    response = checkout(client, buyer_details)
    assert response.status_code == 200

    after = get_listing(listing["id"])
    assert after["quantity_on_hand"] == 0
    assert after["status"] == "ACTIVE"


# K1-9: a sold out item can't be added to the bag
def test_add_to_cart_blocks_sold_out_item(client, make_user, make_listing, login_as):
    listing = make_listing(quantity=0, status="SOLD_OUT")
    login_as(make_user("buyer"))

    response = client.post("/auth/add_to_cart", data={
        "item_id": listing["id"],
        "item_name": listing["title"],
        "price": listing["price"],
        "quantity": 1,
    })
    assert response.status_code == 409
    assert "sold out" in response.get_json()["error"]


# K1-10: you have to be logged in to check out
def test_checkout_requires_login(client, buyer_details):
    response = checkout(client, buyer_details)
    assert response.status_code == 401
