# The Vault Campus Marketplace
# CSC 404 Fall 26'
# Created by Mattie Edozie - 10/26/26
"""
seed_demo_data.py

Purpose:
Loads demo storefronts and listings so the site has something to show.
Images point at files in static/images, which ship with the app, so they work
on the live site without S3.

Safe to run more than once: a storefront that already exists is skipped.

Run it manually:
    python backend/seed_demo_data.py

Or set SEED_DEMO_DATA=true and the app loads it on startup (see app.py).
"""

import secrets

from db import get_connection
from utils.auth_utils import hash_password

# Any fixed number works; it just stops two app workers seeding at the same time
SEED_LOCK_ID = 404_2026

IMG = "/static/images/"

DEMO_STOREFRONTS = [
    {
        "username": "demo_nike",
        "brand_name": "Nike Campus Drop",
        "bio": "Demo storefront: Nike hoodies, jackets and pants.",
        "logo": "nikelogo.png",
        "categories": "Hoodies,Jackets,Pants",
        "listings": [
            {"title": "Nike Tech Fleece Hoodie", "price": 65.00, "images": ["nikehoodie1.png", "nikehoodie2.png"]},
            {"title": "Nike Windrunner Jacket", "price": 80.00, "images": ["nikejacket.png"]},
            {"title": "Nike Tech Fleece Joggers", "price": 55.00, "images": ["nikepants1.png"]},
        ],
    },
    {
        "username": "demo_essentials",
        "brand_name": "Essentials Closet",
        "bio": "Demo storefront: everyday Essentials pieces.",
        "logo": "essentialslogo.png",
        "categories": "Hoodies,Sweats",
        "listings": [
            {"title": "Essentials Pullover Hoodie", "price": 45.00, "images": ["essentials1.png"]},
            {"title": "Essentials Crewneck", "price": 40.00, "images": ["essentials2.png"]},
            {"title": "Essentials Sweatpants", "price": 42.00, "images": ["essentials3.png"]},
            {"title": "Essentials Set", "price": 75.00, "images": ["essentials4.png"]},
        ],
    },
    {
        "username": "demo_vondutch",
        "brand_name": "Von Dutch Vintage",
        "bio": "Demo storefront: vintage Von Dutch finds.",
        "logo": "vondutchlogo.png",
        "categories": "Hats,Tees",
        "listings": [
            {"title": "Von Dutch Trucker Hat", "price": 30.00, "images": ["vondutch1.png"]},
            {"title": "Von Dutch Graphic Tee", "price": 28.00, "images": ["vondutch2.png"]},
            {"title": "Von Dutch Baby Tee", "price": 25.00, "images": ["vondutch3.png"]},
            {"title": "Von Dutch Zip Hoodie", "price": 60.00, "images": ["vondutch4.png"]},
        ],
    },
    {
        "username": "demo_onyx",
        "brand_name": "Onyx Apparel",
        "bio": "Demo storefront: a student-run streetwear brand.",
        "logo": "onyxlogo.jpeg",
        "categories": "Hoodies",
        "listings": [
            {"title": "Onyx Signature Hoodie", "price": 50.00, "images": ["onyxhoodie.png"]},
        ],
    },
]

DEMO_SIZES = [("S", 3), ("M", 5), ("L", 5), ("XL", 3)]


def _get_or_create_user(cur, username):
    cur.execute("SELECT id FROM users WHERE username = %s;", (username,))
    row = cur.fetchone()
    if row:
        return row[0]
    # Demo owners get a random password nobody knows, so the accounts can't be logged into
    cur.execute(
        "INSERT INTO users (username, password, email) VALUES (%s, %s, %s) RETURNING id;",
        (username, hash_password(secrets.token_urlsafe(32)), f"{username}@demo.invalid"),
    )
    return cur.fetchone()[0]


def _create_storefront(cur, owner_id, store):
    previews = [IMG + listing["images"][0] for listing in store["listings"]][:4]
    previews += [None] * (4 - len(previews))
    cur.execute(
        """
        INSERT INTO storefronts
            (owner_id, brand_name, bio, logo_url, banner_url, categories,
             preview_image_1, preview_image_2, preview_image_3, preview_image_4, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
        RETURNING id;
        """,
        (owner_id, store["brand_name"], store["bio"], IMG + store["logo"], IMG + "background.png",
         store["categories"], *previews),
    )
    return cur.fetchone()[0]


def _create_listing(cur, storefront_id, listing):
    total_qty = sum(qty for _, qty in DEMO_SIZES)
    cur.execute(
        """
        INSERT INTO listings
            (storefront_id, title, description, price, fulfillment_type, quantity_on_hand, sizes_available, status)
        VALUES (%s, %s, %s, %s, 'IN_STOCK', %s, %s, 'ACTIVE')
        RETURNING id;
        """,
        (storefront_id, listing["title"], f"Demo listing: {listing['title']}.", listing["price"],
         total_qty, '["S","M","L","XL"]'),
    )
    listing_id = cur.fetchone()[0]

    for i, image in enumerate(listing["images"]):
        cur.execute(
            "INSERT INTO listing_images (listing_id, image_url, is_primary) VALUES (%s, %s, %s);",
            (listing_id, IMG + image, i == 0),
        )
    for size, qty in DEMO_SIZES:
        cur.execute(
            "INSERT INTO listing_sizes (listing_id, size, quantity) VALUES (%s, %s, %s);",
            (listing_id, size, qty),
        )


def seed_demo_data():
    """Creates any demo storefronts that don't exist yet. Returns how many were created."""
    conn = get_connection()
    cur = conn.cursor()
    created = 0
    try:
        # Held until commit, so only one process seeds at a time
        cur.execute("SELECT pg_advisory_xact_lock(%s);", (SEED_LOCK_ID,))

        for store in DEMO_STOREFRONTS:
            owner_id = _get_or_create_user(cur, store["username"])
            cur.execute("SELECT id FROM storefronts WHERE owner_id = %s;", (owner_id,))
            if cur.fetchone():
                continue

            storefront_id = _create_storefront(cur, owner_id, store)
            for listing in store["listings"]:
                _create_listing(cur, storefront_id, listing)
            created += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    return created


if __name__ == "__main__":
    count = seed_demo_data()
    print(f"Demo data loaded: {count} new storefront(s) created.")
