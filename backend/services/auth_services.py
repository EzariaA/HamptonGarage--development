# By Ryan Grimes 2/27/2026
# Register user and validate login
from utils.auth_utils import hash_password, verify_password
import logging  # added - ava

logger = logging.getLogger(__name__)  # added - ava


class AuthService:
    def register_user(self, username, password, email, db_conn):
        # Stores a user's username, hashed password, and email

        # added - ava: handle missing signup fields
        if not username or not password or not email:
            return False, "Username, password, and email are required"

        # Validates Hampton Association, added 2/19/2026 by Ryan Grimes
        # added - ava: require the exact Hampton email domain
        if email.strip().lower().rsplit("@", 1)[-1] != "hamptonu.edu":
            return False, "You Must Use a Hampton University Associated Email"

        hashed_pw = hash_password(password)
        cur = None  # added - ava

        try:
            cur = db_conn.cursor()
            # Parameterized SQL keeps user input separate from SQL commands
            query = """
                INSERT INTO users (username, password, email)
                VALUES (%s, %s, %s)
            """
            cur.execute(query, (username, hashed_pw, email.strip()))
            db_conn.commit()
            return True, "Signup Successful"

        except Exception:
            logger.exception("Registration Error")  # added - ava
            db_conn.rollback()
            return False, "Signup Failed"

        finally:
            # added - ava: close cursor on success or failure
            if cur is not None:
                cur.close()

    def validate_login(self, username, password, db_conn):
        # added - ava: reject missing credentials
        if not username or not password:
            return False, None

        cur = None  # added - ava

        try:
            cur = db_conn.cursor()
            cur.execute(
                "SELECT password, role FROM users WHERE username = %s",
                (username,)
            )
            result = cur.fetchone()

            if result and verify_password(result[0], password):
                return True, result[1]

            return False, None

        except Exception:
            logger.exception("Login Error")  # added - ava
            return False, None

        finally:
            # added - ava: close cursor on success or failure
            if cur is not None:
                cur.close()

    def get_user_cart(self, db_conn, user_id):
        # Retrieves items from the user's persistent database cart
        cur = None  # added - ava

        try:
            cur = db_conn.cursor()
            cur.execute("""
                SELECT item_id, item_name, price, quantity, size
                FROM cart_items WHERE user_id = %s
            """, (user_id,))
            rows = cur.fetchall()

            return [
                {
                    'id': row[0],
                    'name': row[1],
                    'price': float(row[2]),
                    'quantity': row[3],
                    'size': row[4]
                }
                for row in rows
            ]

        except Exception:
            logger.exception(
                "Service Error: Could not fetch cart"
            )  # added - ava
            return []

        finally:
            # added - ava: close cursor on success or failure
            if cur is not None:
                cur.close()

    def clear_user_cart(self, db_conn, user_id):
        # Removes all items from the database cart after checkout
        cur = None  # added - ava

        try:
            cur = db_conn.cursor()
            cur.execute(
                "DELETE FROM cart_items WHERE user_id = %s",
                (user_id,)
            )
            db_conn.commit()

        except Exception:
            logger.exception(
                "Service Error: Could not clear cart"
            )  # added - ava
            db_conn.rollback()  # added - ava

        finally:
            # added - ava: close cursor on success or failure
            if cur is not None:
                cur.close()