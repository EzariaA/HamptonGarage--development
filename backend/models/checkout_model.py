# The Vault Campus Marketplace
# CSC 405 Sp 26'
# Updated by Day Ekoi - 4/22/26 - rewrote to match orders/order_items schema

from db import get_connection


def create_order(user_id, confirmation_number, buyer_first_name, buyer_last_name,
                 buyer_email, buyer_contact, buyer_meeting_location, total_amount):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO orders (user_id, confirmation_number, buyer_first_name, buyer_last_name,
                            buyer_email, buyer_contact, buyer_meeting_location, total_amount, order_status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'SUBMITTED')
        RETURNING id, user_id, confirmation_number, buyer_first_name, buyer_last_name,
                  buyer_email, buyer_contact, buyer_meeting_location, total_amount, order_status, created_at;
    """, (user_id, confirmation_number, buyer_first_name, buyer_last_name,
          buyer_email, buyer_contact, buyer_meeting_location, total_amount))
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return {
        "id": row[0],
        "user_id": row[1],
        "confirmation_number": row[2],
        "buyer_first_name": row[3],
        "buyer_last_name": row[4],
        "buyer_email": row[5],
        "buyer_contact": row[6],
        "buyer_meeting_location": row[7],
        "total_amount": float(row[8]),
        "order_status": row[9],
        "created_at": str(row[10]),
    }


def create_order_item(order_id, listing_id, item_name, quantity, price_at_purchase, selected_size=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO order_items (order_id, listing_id, item_name, quantity, price_at_purchase, selected_size)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, order_id, listing_id, item_name, quantity, price_at_purchase, selected_size;
    """, (order_id, listing_id, item_name, quantity, price_at_purchase, selected_size))
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return {
        "id": row[0],
        "order_id": row[1],
        "listing_id": row[2],
        "item_name": row[3],
        "quantity": row[4],
        "price_at_purchase": float(row[5]),
        "selected_size": row[6],
    }


def get_order_by_confirmation(confirmation_number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, user_id, confirmation_number, buyer_first_name, buyer_last_name,
               buyer_email, buyer_contact, buyer_meeting_location, total_amount, order_status, created_at
        FROM orders
        WHERE confirmation_number = %s;
    """, (confirmation_number,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "user_id": row[1],
        "confirmation_number": row[2],
        "buyer_first_name": row[3],
        "buyer_last_name": row[4],
        "buyer_email": row[5],
        "buyer_contact": row[6],
        "buyer_meeting_location": row[7],
        "total_amount": float(row[8]),
        "order_status": row[9],
        "created_at": str(row[10]),
    }


def get_order_items_by_order_id(order_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, order_id, listing_id, item_name, quantity, price_at_purchase, selected_size
        FROM order_items
        WHERE order_id = %s
        ORDER BY id ASC;
    """, (order_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "id": r[0],
            "order_id": r[1],
            "listing_id": r[2],
            "item_name": r[3],
            "quantity": r[4],
            "price_at_purchase": float(r[5]),
            "selected_size": r[6],
        }
        for r in rows
    ]


def get_orders_by_user_id(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, user_id, confirmation_number, buyer_first_name, buyer_last_name,
               buyer_email, total_amount, order_status, created_at
        FROM orders
        WHERE user_id = %s
        ORDER BY created_at DESC;
    """, (user_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "id": r[0],
            "user_id": r[1],
            "confirmation_number": r[2],
            "buyer_first_name": r[3],
            "buyer_last_name": r[4],
            "buyer_email": r[5],
            "total_amount": float(r[6]),
            "order_status": r[7],
            "created_at": str(r[8]),
        }
        for r in rows
    ]


def remove_purchased_from_wishlist(user_id, listing_ids):
    """
    Removes wishlist entries for listings the user just purchased.
    Uses listing_id matching only — the wishlist has a UNIQUE(user_id, listing_id)
    constraint so there is at most one entry per listing per user.
    """
    if not listing_ids:
        return {"deleted_count": 0}
    # Filter out None values
    valid_ids = [int(lid) for lid in listing_ids if lid is not None]
    if not valid_ids:
        return {"deleted_count": 0}
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM wishlist WHERE user_id = %s AND listing_id = ANY(%s);",
        (user_id, valid_ids)
    )
    deleted_count = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return {"deleted_count": deleted_count}


def clear_cart_for_user(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM cart_items WHERE user_id = %s;", (user_id,))
    deleted_count = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return {"deleted_count": deleted_count}


def check_listing_availability(listing_id, quantity_requested):
    """Raises if the listing is sold out or has insufficient stock. Skips made-to-order items."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT title, status, quantity_on_hand, is_made_to_order FROM listings WHERE id = %s",
        (listing_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        raise Exception(f"Item (ID {listing_id}) is no longer available.")
    title, status, qty_on_hand, is_made_to_order = row
    if is_made_to_order:
        return
    if status == "SOLD_OUT":
        raise Exception(f'"{title}" is sold out.')
    if qty_on_hand is not None and int(qty_on_hand) < quantity_requested:
        raise Exception(
            f'"{title}" only has {qty_on_hand} in stock (you requested {quantity_requested}).'
        )


def update_listing_size_inventory(listing_id, size, purchased_qty):
    """Decrements per-size inventory and syncs listing quantity_on_hand after purchase."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT quantity FROM listing_sizes WHERE listing_id = %s AND size = %s",
        (listing_id, size)
    )
    size_row = cur.fetchone()
    if size_row is None or int(size_row[0]) < purchased_qty:
        cur.close()
        conn.close()
        available = int(size_row[0]) if size_row else 0
        raise Exception(
            f"Insufficient stock for listing {listing_id} size '{size}': "
            f"requested {purchased_qty}, available {available}."
        )
    cur.execute("""
        UPDATE listing_sizes
        SET quantity = GREATEST(0, quantity - %s)
        WHERE listing_id = %s AND size = %s;
    """, (purchased_qty, listing_id, size))
    cur.execute("""
        SELECT COALESCE(SUM(quantity), 0) FROM listing_sizes WHERE listing_id = %s;
    """, (listing_id,))
    total_qty = int(cur.fetchone()[0])
    new_status = "SOLD_OUT" if total_qty == 0 else None
    cur.execute("""
        UPDATE listings
        SET quantity_on_hand = %s,
            status = COALESCE(%s, CASE WHEN status = 'SOLD_OUT' AND %s > 0 THEN 'ACTIVE' ELSE status END),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s AND (is_made_to_order = FALSE OR is_made_to_order IS NULL);
    """, (total_qty, new_status, total_qty, listing_id))
    conn.commit()
    cur.close()
    conn.close()



# Added by Kyle Lewis 10/26/26 - Iteration 3 (K1)
# Reduce stock on completed orders and block checkout for sold out items.
#
# Before this, the order was saved first and then the stock was updated, and if the
# stock update failed it was just logged and ignored. Now everything is done with ONE
# connection and only saved (commit) at the end. If anything is wrong, rollback()
# undoes all of it so no order is made and no stock is taken.

class InventoryError(Exception):
    # used when an item is sold out or there isn't enough stock
    pass


def place_order_with_inventory(user_id, confirmation_number, buyer, cart_items, total_amount):
    """
    Checks stock, saves the order + order items, and lowers the stock, all at once.

    buyer = {first_name, last_name, email, contact, meeting_location}
    cart_items = list of {listing_id, item_name, quantity, price, size}
    """
    conn = get_connection()
    cur = conn.cursor()

    try:
        # Step 1: add up how many of each listing (and each size) are in the cart.
        # This way 2 separate cart lines of the same item get counted together.
        listing_totals = {}
        size_totals = {}
        for item in cart_items:
            listing_id = item["listing_id"]
            if listing_id is None:
                continue
            listing_totals[listing_id] = listing_totals.get(listing_id, 0) + item["quantity"]
            if item["size"]:
                key = (listing_id, item["size"])
                size_totals[key] = size_totals.get(key, 0) + item["quantity"]

        # Step 2: check every listing before saving anything.
        # FOR UPDATE locks the row until we commit, so two people can't buy the last one at the same time.
        listing_info = {}
        for listing_id in listing_totals:
            cur.execute("""
                SELECT title, status, quantity_on_hand, is_made_to_order
                FROM listings WHERE id = %s FOR UPDATE;
            """, (listing_id,))
            row = cur.fetchone()

            if row is None or row[1] in ("DELETED", "INACTIVE"):
                raise InventoryError(f"Item (ID {listing_id}) is no longer available.")

            title, status, qty_on_hand, is_made_to_order = row
            listing_info[listing_id] = row

            # made to order items don't have stock, so skip the checks
            if is_made_to_order:
                continue

            wanted = listing_totals[listing_id]
            if status == "SOLD_OUT" or (qty_on_hand is not None and qty_on_hand <= 0):
                raise InventoryError(f'"{title}" is sold out.')
            if qty_on_hand is not None and qty_on_hand < wanted:
                raise InventoryError(f'"{title}" only has {qty_on_hand} in stock (you requested {wanted}).')

        # Step 3: check the stock for each size (only if that listing has sizes saved)
        for (listing_id, size), wanted in size_totals.items():
            title = listing_info[listing_id][0]
            is_made_to_order = listing_info[listing_id][3]
            if is_made_to_order:
                continue

            cur.execute("SELECT COUNT(*) FROM listing_sizes WHERE listing_id = %s;", (listing_id,))
            has_sizes = cur.fetchone()[0] > 0
            if not has_sizes:
                continue

            cur.execute("""
                SELECT quantity FROM listing_sizes
                WHERE listing_id = %s AND size = %s FOR UPDATE;
            """, (listing_id, size))
            size_row = cur.fetchone()
            available = size_row[0] if size_row else 0

            if available == 0:
                raise InventoryError(f'"{title}" is sold out in size {size}.')
            if available < wanted:
                raise InventoryError(
                    f'"{title}" only has {available} left in size {size} (you requested {wanted}).'
                )

        # Step 4: everything is in stock, so save the order
        cur.execute("""
            INSERT INTO orders (user_id, confirmation_number, buyer_first_name, buyer_last_name,
                                buyer_email, buyer_contact, buyer_meeting_location, total_amount, order_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'SUBMITTED')
            RETURNING id, user_id, confirmation_number, buyer_first_name, buyer_last_name,
                      buyer_email, buyer_contact, buyer_meeting_location, total_amount, order_status, created_at;
        """, (user_id, confirmation_number, buyer["first_name"], buyer["last_name"],
              buyer["email"], buyer["contact"], buyer["meeting_location"], total_amount))
        row = cur.fetchone()
        order = {
            "id": row[0],
            "user_id": row[1],
            "confirmation_number": row[2],
            "buyer_first_name": row[3],
            "buyer_last_name": row[4],
            "buyer_email": row[5],
            "buyer_contact": row[6],
            "buyer_meeting_location": row[7],
            "total_amount": float(row[8]),
            "order_status": row[9],
            "created_at": str(row[10]),
        }

        # save each item in the order
        order_items = []
        for item in cart_items:
            cur.execute("""
                INSERT INTO order_items (order_id, listing_id, item_name, quantity, price_at_purchase, selected_size)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, order_id, listing_id, item_name, quantity, price_at_purchase, selected_size;
            """, (order["id"], item["listing_id"], item["item_name"], item["quantity"],
                  item["price"], item["size"]))
            row = cur.fetchone()
            order_items.append({
                "id": row[0],
                "order_id": row[1],
                "listing_id": row[2],
                "item_name": row[3],
                "quantity": row[4],
                "price_at_purchase": float(row[5]),
                "selected_size": row[6],
            })

        # Step 5: lower the stock for each size that was bought
        for (listing_id, size), qty in size_totals.items():
            if listing_info[listing_id][3]:  # made to order
                continue
            cur.execute("""
                UPDATE listing_sizes SET quantity = quantity - %s
                WHERE listing_id = %s AND size = %s;
            """, (qty, listing_id, size))

        # Step 6: lower the total stock, and mark it SOLD_OUT if it hits 0
        for listing_id, qty in listing_totals.items():
            if listing_info[listing_id][3]:  # made to order
                continue

            cur.execute("""
                UPDATE listings
                SET quantity_on_hand = quantity_on_hand - %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND quantity_on_hand IS NOT NULL;
            """, (qty, listing_id))

            # check if it's sold out now (total is 0, or every size is 0)
            cur.execute("SELECT quantity_on_hand FROM listings WHERE id = %s;", (listing_id,))
            new_qty = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*), COALESCE(SUM(quantity), 0) FROM listing_sizes WHERE listing_id = %s;",
                        (listing_id,))
            size_count, size_sum = cur.fetchone()

            if (new_qty is not None and new_qty <= 0) or (size_count > 0 and size_sum <= 0):
                cur.execute("UPDATE listings SET status = 'SOLD_OUT' WHERE id = %s;", (listing_id,))

        # everything worked, so save it all
        conn.commit()
        cur.close()
        conn.close()
        return {"order": order, "order_items": order_items}

    except Exception:
        # something went wrong, undo everything
        conn.rollback()
        cur.close()
        conn.close()
        raise
