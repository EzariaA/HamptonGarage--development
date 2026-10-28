# The Vault Campus Marketplace
# CSC 404 Fa 26'
# Created by Kyle Lewis 10/26/26 - Iteration 3 (Mk3)

"""
seed_data.py

Purpose:
Puts starter data into the database. This replaces the old hardcoded
admin/admin123 login that was in auth_controller.py.

It will:
- Create an admin user (role = 'admin')

The admin password is NOT written in the code. It comes from the .env file
or the terminal so nobody can see it on GitHub.
    ADMIN_USERNAME  (default: admin)
    ADMIN_EMAIL     (default: admin@hamptonu.edu)
    ADMIN_PASSWORD  (you have to set this one)

Run this file after init_db.py:
    python3 backend/init_db.py
    ADMIN_PASSWORD='pick-a-password' python3 backend/seed_data.py

It is ok to run it more than once, it won't make duplicates.
"""

import os

from db import get_connection
from utils.auth_utils import hash_password


def seed_admin(conn):
    username = os.getenv("ADMIN_USERNAME", "admin")
    email = os.getenv("ADMIN_EMAIL", "admin@hamptonu.edu")
    password = os.getenv("ADMIN_PASSWORD")

    # stop if there is no password set
    if not password:
        print("SEED: ADMIN_PASSWORD is not set, so the admin user was not created.")
        return None

    cur = conn.cursor()

    # if the username is already there, just make sure it is an admin
    cur.execute("""
        INSERT INTO users (username, password, email, role)
        VALUES (%s, %s, %s, 'admin')
        ON CONFLICT (username) DO UPDATE SET role = 'admin'
        RETURNING id;
    """, (username, hash_password(password), email))

    admin_id = cur.fetchone()[0]
    conn.commit()
    cur.close()

    print(f"SEED: admin user '{username}' is ready.")
    return admin_id


if __name__ == "__main__":
    conn = get_connection()
    seed_admin(conn)
    conn.close()
