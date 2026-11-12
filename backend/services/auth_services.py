#By Ryan Grimes 2/27/2026
#Register user and validate login
from utils.auth_utils import hash_password, verify_password
from datetime import datetime, timedelta  # added - Kyle Lewis 11/11/26
import logging  # added - ava
logger = logging.getLogger(__name__)  # added - ava

# Email domains allowed to sign up - added by Kyle Lewis 11/11/26
# The Requirements (1.2.1 Student Validation) allow both of these.
ALLOWED_EMAIL_DOMAINS = ["my.hamptonu.edu", "hamptonu.edu"]

# Admin lockout settings - added by Kyle Lewis 11/11/26
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
class AuthService:
    # Added by Mason Johnson 10/26/26 - simple email format check (one @, something before it, a dot after it, no spaces)
    def is_valid_email_format(self, email):
        if " " in email or email.count("@") != 1:
            return False
        name, domain = email.split("@")
        if not name or "." not in domain:
            return False
        if domain.startswith(".") or domain.endswith("."):
            return False
        return True

    # Added by Mason Johnson 10/27/26
    # The part after the @ must match exactly. (The old check only looked at how the
    # email ended, so even name@fakehamptonu.edu was let through.)
    # Updated by Kyle Lewis 11/11/26 - both Hampton domains are allowed, per Requirements 1.2.1
    # Example: "jsmith@my.hamptonu.edu" -> True, "jsmith@hamptonu.edu" -> True,
    #          "jsmith@fakehamptonu.edu" -> False
    def is_student_email(self, email):
        if not email or email.count("@") != 1:
            return False
        name, domain = email.split("@")
        if not name:
            return False
        return domain.lower() in ALLOWED_EMAIL_DOMAINS

    # Added by Mason Johnson 10/26/26
    # Checks every signup field and returns a dictionary of field name -> error message.
    # An empty dictionary means everything is OK and the account can be created.
    def validate_signup(self, username, email, password, db_conn):
        errors = {}

        # Username
        if not username:
            errors["username"] = "Enter a username."
        elif len(username) > 50:
            errors["username"] = "Username must be 50 characters or fewer."

        # Email
        if not email:
            errors["email"] = "Enter your email."
        elif not self.is_valid_email_format(email) or len(email) > 100:
            errors["email"] = "Enter a valid email address, like name@my.hamptonu.edu."
        elif not self.is_student_email(email):
            errors["email"] = "You must use your Hampton email (ending in @my.hamptonu.edu or @hamptonu.edu)."

        # Password: at least 8 characters with at least one letter and one number
        if not password:
            errors["password"] = "Enter a password."
        elif len(password) < 8:
            errors["password"] = "Password must be at least 8 characters."
        else:
            has_letter = False
            has_number = False
            for char in password:
                if char.isalpha():
                    has_letter = True
                if char.isdigit():
                    has_number = True
            if not has_letter or not has_number:
                errors["password"] = "Password must include at least one letter and one number."

        # Duplicate checks (only for fields that passed the checks above)
        if "username" not in errors or "email" not in errors:
            try:
                cur = db_conn.cursor()
                if "username" not in errors:
                    cur.execute("SELECT id FROM users WHERE username = %s", (username,))
                    if cur.fetchone():
                        errors["username"] = "That username is already taken."
                if "email" not in errors:
                    cur.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(%s)", (email,))
                    if cur.fetchone():
                        errors["email"] = "An account with this email already exists."
                cur.close()
            except Exception as e:
                logger.warning(f"Signup check error: {e}")
                errors["general"] = "Something went wrong. Please try again."

        return errors

    def register_user(self, username, password, email, db_conn): #Stores a user's unique ID, username, password, and email into the database
        if not self.is_student_email(email): #Validates Hampton Assocation, added 2/19/2026 by Ryan Grimes. Updated by Mason Johnson 10/27/26 to require @my.hamptonu.edu. Kyle Lewis 11/11/26: @hamptonu.edu allowed too
            logger.warning(f"You Must Use a Hampton Email (@my.hamptonu.edu or @hamptonu.edu)")
            return False, "You Must Use a Hampton Email (@my.hamptonu.edu or @hamptonu.edu)"

        hashed_pw = hash_password(password)
        try:
            cur = db_conn.cursor() #Creates a point for data to be entered into database
            query = "INSERT INTO users (username, password, email) VALUES (%s, %s, %s)" #Enters data into SQL database. '%s' prevents SQLi by forcing the database to treat user input strictly as data, not as executable SQL code
            cur.execute(query, (username, hashed_pw, email)) #Inputs data at cursor point
            db_conn.commit() #Saves changes
            cur.close() #Closes cursor
            return True, "Signup Successful"
        except Exception as e:
            logger.warning(f"Registration Error: {e}")
            db_conn.rollback() #If connection fails, all changes are voided to prevent saving partial data
            return False, "Signup Failed"
        
    def validate_login(self, username, password, db_conn):
        try: 
            cur = db_conn.cursor() #Creates a pointer
            cur.execute("SELECT password, role FROM users WHERE username = %s", (username,)) #Has pointer search for occurence of entered credentials
            result = cur.fetchone() #Fetches the row of data that matches the query
            cur.close() #Closes cursor

            if result and verify_password(result[0], password): #If username and password hash match return true
                return True, result [1]
        
            return False, None
        except Exception as e:
            logger.warning(f"Login Error: {e}")
            return False, None
    
    # Added by Kyle Lewis 11/11/26 - admin login with lockout
    # After 5 wrong passwords in a row the account is locked out of the admin login for
    # 15 minutes. While locked, even the right password is refused. A good login resets the count.
    # Returns "ok", "locked", or "invalid".
    # now is only passed in by the tests so they don't have to wait 15 real minutes.
    def check_admin_login(self, username, password, db_conn, now=None):
        if self.is_account_locked(username, db_conn, now):
            return "locked"

        success, role = self.validate_login(username, password, db_conn)
        if success and role and role.lower() == "admin":
            self.reset_failed_logins(username, db_conn)
            return "ok"

        self.record_failed_login(username, db_conn, now)
        if self.is_account_locked(username, db_conn, now):
            return "locked"
        return "invalid"

    # Added by Kyle Lewis 11/11/26 - True if the account is locked right now
    def is_account_locked(self, username, db_conn, now=None):
        if now is None:
            now = datetime.now()
        cur = db_conn.cursor()
        cur.execute("SELECT locked_until FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        cur.close()
        if row is None or row[0] is None:
            return False
        return now < row[0]

    # Added by Kyle Lewis 11/11/26 - adds 1 to the failed count and locks the account on the 5th
    def record_failed_login(self, username, db_conn, now=None):
        if now is None:
            now = datetime.now()
        cur = db_conn.cursor()
        cur.execute("""
            UPDATE users SET failed_login_attempts = COALESCE(failed_login_attempts, 0) + 1
            WHERE username = %s
            RETURNING failed_login_attempts;
        """, (username,))
        row = cur.fetchone()
        if row and row[0] >= MAX_FAILED_LOGINS:
            # lock it and start the count over, so they get 5 new tries after the 15 minutes
            locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            cur.execute("""
                UPDATE users SET locked_until = %s, failed_login_attempts = 0
                WHERE username = %s;
            """, (locked_until, username))
            logger.warning(f"ADMIN LOCKOUT: '{username}' locked for {LOCKOUT_MINUTES} minutes after {MAX_FAILED_LOGINS} failed admin logins")
        db_conn.commit()
        cur.close()

    # Added by Kyle Lewis 11/11/26 - clears the failed count and any lock after a good login
    def reset_failed_logins(self, username, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            UPDATE users SET failed_login_attempts = 0, locked_until = NULL
            WHERE username = %s;
        """, (username,))
        db_conn.commit()
        cur.close()

    def get_user_cart(self, db_conn, user_id): #Retrieves all items from the persistent database for a specific user.
        try:
            cur = db_conn.cursor()
            cur.execute("""
                SELECT item_id, item_name, price, quantity, size 
                FROM cart_items WHERE user_id = %s
            """, (user_id,))
            rows = cur.fetchall()
            return [{'id': r[0], 'name': r[1], 'price': float(r[2]), 'quantity': r[3], 'size': r[4]} for r in rows]
        except Exception as e:
            logger.warning(f"Service Error: Could not fetch cart: {e}")
            return []

    def clear_user_cart(self, db_conn, user_id): #Removes all items from the database bag (useful after checkout).
        try:
            cur = db_conn.cursor()
            cur.execute("DELETE FROM cart_items WHERE user_id = %s", (user_id,))
            db_conn.commit()
        except Exception as e:
            logger.warning(f"Service Error: Could not clear cart: {e}")