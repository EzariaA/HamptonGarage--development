# backend/tests/test_admin_auth.py
# Kyle Lewis - Iteration 3 (Mk3)
# Tests that the admin123 backdoor and the debug route are gone, and the seeded admin works
# (Test IDs MK3-1 to MK3-7)

from db import get_connection
from seed_data import seed_admin


def admin_login(client, username, password):
    return client.post("/auth/admin-login", data={"username": username, "password": password})


# MK3-1: the admin made by seed_data.py can log in
def test_seeded_admin_can_log_in(client, admin_user):
    response = admin_login(client, admin_user["username"], admin_user["password"])
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin")

    with client.session_transaction() as session:
        assert session["role"] == "admin"
        assert session["user_id"] == admin_user["id"]


# MK3-2: the old admin / admin123 login doesn't work anymore
def test_admin123_backdoor_is_removed(client):
    response = admin_login(client, "admin", "admin123")
    assert b"Invalid Admin Credentials" in response.data

    with client.session_transaction() as session:
        assert "role" not in session


# MK3-3: a normal user can't log in through the admin login
def test_regular_user_cannot_use_admin_login(client, make_user):
    user = make_user("regular_student")
    response = admin_login(client, user["username"], user["password"])
    assert b"Invalid Admin Credentials" in response.data

    with client.session_transaction() as session:
        assert session.get("role") != "admin"


# MK3-4: the admin username with the wrong password doesn't work
def test_admin_wrong_password_is_rejected(client, admin_user):
    response = admin_login(client, admin_user["username"], "wrong-password")
    assert b"Invalid Admin Credentials" in response.data

    with client.session_transaction() as session:
        assert "role" not in session


# MK3-5: /auth/debug/session is gone
def test_debug_session_route_is_removed(client, make_user, login_as):
    login_as(make_user("curious_user"))
    response = client.get("/auth/debug/session")
    assert response.status_code == 404


# MK3-6: the admin password is saved hashed, and running the seed again doesn't make a second admin
def test_seed_hashes_password_and_can_run_twice(admin_user):
    conn = get_connection()
    seed_admin(conn)  # run it a second time

    cur = conn.cursor()
    cur.execute("SELECT password, role FROM users WHERE username = %s;", (admin_user["username"],))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    assert len(rows) == 1
    assert rows[0][1] == "admin"
    assert rows[0][0] != admin_user["password"]
    assert rows[0][0].startswith("pbkdf2:sha256")


# MK3-7: admin routes block people who aren't admins
def test_admin_routes_block_non_admins(client, make_user, login_as):
    response = client.get("/admin/users")
    assert response.status_code == 401

    login_as(make_user("not_an_admin"))
    response = client.get("/admin/users")
    assert response.status_code == 403
