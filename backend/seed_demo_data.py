# The Vault Campus Marketplace
# CSC 404 Fall 26'
# Created by Mattie Edozie - 10/26/26
"""
seed_demo_data.py

Purpose:
Fills the site with demo storefronts and listings so it isn't empty.
"Seeding" just means putting starter data into the database.

The pictures are files already in static/images, which get uploaded to AWS
with the rest of the app, so they show up on the live site without S3.

It's safe to run more than once: if a demo storefront is already there, it's skipped.

Run it by hand:
    python backend/seed_demo_data.py

Or set SEED_DEMO_DATA=true and app.py runs it every time the app starts.
"""

import secrets

from db import get_connection
from utils.auth_utils import hash_password

# All the demo images live in static/images
IMG = "/static/images/"

# Every listing gets these sizes and this many of each
DEMO_SIZES = [("S", 3), ("M", 5), ("L", 5), ("XL", 3)]

# The demo stores. Each one gets its own demo owner account.
DEMO_STOREFRONTS = [
    {
        "username": "demo_nike",
        "brand_name": "Nike Campus Drop",
        "bio": "Demo storefront: Nike hoodies, jackets and pants.",
        "logo": "nikelogo.png",
        "categories": "Athleisure,Streetwear",
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
        "categories": "Casual,Streetwear",
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
        "categories": "Vintage,Retro,Accessories",
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
        "categories": "Streetwear",
        "listings": [
            {"title": "Onyx Signature Hoodie", "price": 50.00, "images": ["onyxhoodie.png"]},
        ],
    },
]


def get_or_create_demo_user(cur, username):
    """Finds the demo owner account, or makes it if it doesn't exist. Returns the user id."""
    cur.execute("SELECT id FROM users WHERE username = %s;", (username,))
    row = cur.fetchone()
    if row:
        return row[0]

    # Random password that nobody knows, so no one can log in as a demo owner.
    # ".invalid" emails can never belong to a real person.
    random_password = secrets.token_urlsafe(32)
    cur.execute(
        "INSERT INTO users (username, password, email) VALUES (%s, %s, %s) RETURNING id;",
        (username, hash_password(random_password), username + "@demo.invalid"),
    )
    return cur.fetchone()[0]


def create_demo_storefront(cur, owner_id, store):
    """Adds one storefront. Returns its id."""
    # The storefront card shows up to 4 preview pictures. Use each listing's first picture.
    previews = [None, None, None, None]
    for i in range(min(4, len(store["listings"]))):
        previews[i] = IMG + store["listings"][i]["images"][0]

    cur.execute(
        """
        INSERT INTO storefronts
            (owner_id, brand_name, bio, logo_url, banner_url, categories,
             preview_image_1, preview_image_2, preview_image_3, preview_image_4, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
        RETURNING id;
        """,
        (owner_id, store["brand_name"], store["bio"], IMG + store["logo"], IMG + "background.png",
         store["categories"], previews[0], previews[1], previews[2], previews[3]),
    )
    return cur.fetchone()[0]


def create_demo_listing(cur, storefront_id, listing):
    """Adds one listing with its pictures and sizes."""
    total_quantity = 0
    for size, quantity in DEMO_SIZES:
        total_quantity = total_quantity + quantity

    cur.execute(
        """
        INSERT INTO listings
            (storefront_id, title, description, price, fulfillment_type, quantity_on_hand, sizes_available, status)
        VALUES (%s, %s, %s, %s, 'IN_STOCK', %s, %s, 'ACTIVE')
        RETURNING id;
        """,
        (storefront_id, listing["title"], "Demo listing: " + listing["title"] + ".", listing["price"],
         total_quantity, '["S","M","L","XL"]'),
    )
    listing_id = cur.fetchone()[0]

    # Pictures: the first one is the main (primary) picture
    is_first = True
    for image in listing["images"]:
        cur.execute(
            "INSERT INTO listing_images (listing_id, image_url, is_primary) VALUES (%s, %s, %s);",
            (listing_id, IMG + image, is_first),
        )
        is_first = False

    # How many of each size are in stock
    for size, quantity in DEMO_SIZES:
        cur.execute(
            "INSERT INTO listing_sizes (listing_id, size, quantity) VALUES (%s, %s, %s);",
            (listing_id, size, quantity),
        )


def seed_demo_data():
    """Adds any demo storefronts that aren't in the database yet. Returns how many it added."""
    conn = get_connection()
    cur = conn.cursor()
    created = 0

    try:
        for store in DEMO_STOREFRONTS:
            owner_id = get_or_create_demo_user(cur, store["username"])

            # Already has a storefront? Skip it so we don't make doubles.
            cur.execute("SELECT id FROM storefronts WHERE owner_id = %s;", (owner_id,))
            if cur.fetchone():
                continue

            storefront_id = create_demo_storefront(cur, owner_id, store)
            for listing in store["listings"]:
                create_demo_listing(cur, storefront_id, listing)
            created = created + 1

        # Save everything at once
        conn.commit()
    except Exception:
        # Something broke, so undo everything from this run
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    return created


if __name__ == "__main__":
    count = seed_demo_data()
    print("Demo data loaded:", count, "new storefront(s) created.")
