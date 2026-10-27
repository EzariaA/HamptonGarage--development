# backend/tests/conftest.py
# Kyle Lewis - Iteration 3

"""
conftest.py

Purpose:
pytest runs this file automatically before the tests. It holds the setup
that every test file shares (these are called "fixtures").

It will:
- Point the app at a SEPARATE test database (vault_test) so tests never touch the real data
- Create the tables one time when the tests start
- Empty all the tables before each test so every test starts clean
- Give the tests helpers like a test client, test users, an admin, and listings

Before running the tests the first time, install pytest and make the test database:
    pip install pytest pytest-cov
    createdb vault_test
Then run all the tests from the project folder:
    pytest
"""

import os

import pytest

# These have to be set BEFORE app.py and db.py are imported, because db.py reads them.
# load_dotenv() won't overwrite these, so your .env can't point the tests at the real database.
os.environ["DB_NAME"] = os.getenv("TEST_DB_NAME", "vault_test")
os.environ["DB_HOST"] = os.getenv("TEST_DB_HOST", "localhost")
os.environ["DB_PORT"] = os.getenv("TEST_DB_PORT", "5432")
os.environ["DB_USER"] = os.getenv("TEST_DB_USER", "postgres")
os.environ["DB_PASSWORD"] = os.getenv("TEST_DB_PASSWORD", "postgres")
os.environ["DB_SSLMODE"] = os.getenv("TEST_DB_SSLMODE", "disable")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ["ADMIN_USERNAME"] = "test_admin"
os.environ["ADMIN_EMAIL"] = "test_admin@hamptonu.edu"
os.environ["ADMIN_PASSWORD"] = "Adm1n-test-only!"

# safety check: only run on a database that ends in _test
if not os.environ["DB_NAME"].endswith("_test"):
    raise RuntimeError("The test database name has to end in _test (example: vault_test)")

from app import create_app
from db import get_connection
from init_db import create_vault_tables
from seed_data import seed_admin
from utils.auth_utils import hash_password


# Runs one time when the tests start - makes sure the database is there and creates the tables
@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    try:
        conn = get_connection()
        conn.close()
    except Exception as e:
        pytest.exit(f"Could not connect to the test database. Is PostgreSQL running and did you run 'createdb vault_test'? Error: {e}")
    create_vault_tables()


# Runs before EVERY test - empties all the tables so the tests don't affect each other
@pytest.fixture(autouse=True)
def clean_database():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        TRUNCATE order_items, orders, cart_items, returns, wishlist, purchases,
                 listing_sizes, listing_images, listings, storefronts, users
        RESTART IDENTITY CASCADE;
    """)
    conn.commit()
    cur.close()
    conn.close()


@pytest.fixture
def app():
    app = create_app()
    app.config.update(TESTING=True)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


# Makes a user in the test database. Use it like: user = make_user("alice")
@pytest.fixture
def make_user():
    def _make_user(username="test_user", password="Passw0rd!", role="user"):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password, email, role) VALUES (%s, %s, %s, %s) RETURNING id;",
            (username, hash_password(password), username + "@hamptonu.edu", role),
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return {"id": user_id, "username": username, "password": password, "role": role}
    return _make_user


# The admin user made by seed_data.py
@pytest.fixture
def admin_user():
    conn = get_connection()
    admin_id = seed_admin(conn)
    conn.close()
    return {
        "id": admin_id,
        "username": os.environ["ADMIN_USERNAME"],
        "password": os.environ["ADMIN_PASSWORD"],
        "role": "admin",
    }


# Makes a listing (and a seller + storefront the first time).
# Use it like: listing = make_listing(quantity=5, sizes={"S": 2, "M": 3})
@pytest.fixture
def make_listing(make_user):
    storefront = {}

    def _make_listing(title="Test Hoodie", price=40.00, quantity=1, sizes=None,
                      status="ACTIVE", made_to_order=False):
        conn = get_connection()
        cur = conn.cursor()

        # make the seller and storefront only once
        if "id" not in storefront:
            seller = make_user("test_seller")
            cur.execute(
                "INSERT INTO storefronts (owner_id, brand_name) VALUES (%s, 'Test Brand') RETURNING id;",
                (seller["id"],),
            )
            storefront["id"] = cur.fetchone()[0]

        if made_to_order:
            fulfillment_type = "PREORDER"
        else:
            fulfillment_type = "IN_STOCK"

        cur.execute("""
            INSERT INTO listings (storefront_id, title, price, fulfillment_type,
                                  quantity_on_hand, status, is_made_to_order)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id;
        """, (storefront["id"], title, price, fulfillment_type, quantity, status, made_to_order))
        listing_id = cur.fetchone()[0]

        if sizes:
            for size, size_qty in sizes.items():
                cur.execute(
                    "INSERT INTO listing_sizes (listing_id, size, quantity) VALUES (%s, %s, %s);",
                    (listing_id, size, size_qty),
                )

        conn.commit()
        cur.close()
        conn.close()
        return {"id": listing_id, "title": title, "price": price}

    return _make_listing


# Looks up a listing's stock and status after a test runs
@pytest.fixture
def get_listing():
    def _get_listing(listing_id):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT quantity_on_hand, status FROM listings WHERE id = %s;", (listing_id,))
        qty, status = cur.fetchone()
        cur.execute("SELECT size, quantity FROM listing_sizes WHERE listing_id = %s;", (listing_id,))
        sizes = dict(cur.fetchall())
        cur.close()
        conn.close()
        return {"quantity_on_hand": qty, "status": status, "sizes": sizes}
    return _get_listing


# Logs the test client in as a user (and can put items in their cart)
@pytest.fixture
def login_as(client):
    def _login_as(user, cart=None):
        with client.session_transaction() as session:
            session["user"] = user["username"]
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["cart"] = cart or []
        return client
    return _login_as


# Checkout form info that is filled out correctly
@pytest.fixture
def buyer_details():
    return {
        "first_name": "Test",
        "last_name": "Buyer",
        "email": "test_buyer@hamptonu.edu",
        "contact": "757-555-0100",
        "meeting_location": "Student Center",
    }
