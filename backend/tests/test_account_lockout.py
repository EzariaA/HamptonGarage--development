# backend/tests/test_account_lockout.py
# Created by Kyle Lewis 11/11/26 - Iteration 4
# Tests for the admin lockout: locks after 5 failed logins, unlocks after 15 minutes,
# and the failed count resets after a successful login. (Test IDs LO-1 to LO-5)

from datetime import datetime, timedelta

from db import get_connection
from services.auth_services import AuthService

service = AuthService()


def admin_login(user, password, now=None):
    conn = get_connection()
    result = service.check_admin_login(user["username"], password, conn, now)
    conn.close()
    return result


def is_locked(user, now=None):
    conn = get_connection()
    locked = service.is_account_locked(user["username"], conn, now)
    conn.close()
    return locked


# LO-1: 4 wrong passwords don't lock the account, the 5th one does
def test_admin_locks_after_5_failed_logins(admin_user):
    for i in range(4):
        assert admin_login(admin_user, "wrong-password") == "invalid"
    assert is_locked(admin_user) == False

    assert admin_login(admin_user, "wrong-password") == "locked"
    assert is_locked(admin_user) == True


# LO-2: while locked, even the correct password is refused
def test_correct_password_refused_while_locked(admin_user):
    for i in range(5):
        admin_login(admin_user, "wrong-password")

    assert admin_login(admin_user, admin_user["password"]) == "locked"


# LO-3: the lock lasts 15 minutes, then the admin can log in again
def test_admin_unlocks_after_15_minutes(admin_user):
    start = datetime.now()
    for i in range(5):
        admin_login(admin_user, "wrong-password", now=start)

    # still locked at 14 minutes
    fourteen_min_later = start + timedelta(minutes=14)
    assert admin_login(admin_user, admin_user["password"], now=fourteen_min_later) == "locked"

    # unlocked after 15 minutes, and the right password works
    fifteen_min_later = start + timedelta(minutes=15, seconds=1)
    assert is_locked(admin_user, now=fifteen_min_later) == False
    assert admin_login(admin_user, admin_user["password"], now=fifteen_min_later) == "ok"


# LO-4: a successful login resets the count, so 4 more wrong tries don't lock it
def test_failed_count_resets_after_successful_login(admin_user):
    for i in range(4):
        admin_login(admin_user, "wrong-password")
    assert admin_login(admin_user, admin_user["password"]) == "ok"

    for i in range(4):
        admin_login(admin_user, "wrong-password")
    assert is_locked(admin_user) == False

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT failed_login_attempts FROM users WHERE username = %s", (admin_user["username"],))
    assert cur.fetchone()[0] == 4
    cur.close()
    conn.close()


# LO-5: the admin login page shows the locked message after 5 failed tries
def test_admin_login_page_shows_locked_message(client, admin_user):
    for i in range(5):
        response = client.post("/auth/admin-login", data={"username": admin_user["username"], "password": "wrong"})

    assert b"locked for 15 minutes" in response.data
    with client.session_transaction() as session:
        assert "role" not in session
