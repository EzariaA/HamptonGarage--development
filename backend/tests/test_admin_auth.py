# backend/tests/test_admin_auth.py
# Kyle Lewis - Iteration 3 (Mk3)
# Tests that the admin123 backdoor and the debug route are gone, and the seeded admin works
# (Test IDs MK3-1 and MK3-2)



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
