# Created by Kyle Lewis 11/11/26 - Iteration 4
# Checks the session timeout (Test IDs ST-1 and ST-2)
# ST-1 checks session lifetime in app.py (HG-121).

from datetime import timedelta


# ST-1: the app sets its own session lifetime (Flask's default is 31 days)
def test_session_lifetime_is_set(app):
    lifetime = app.config["PERMANENT_SESSION_LIFETIME"]
    if not isinstance(lifetime, timedelta):
        lifetime = timedelta(seconds=lifetime)
    assert lifetime > timedelta(0)
    assert lifetime != timedelta(days=31)


# ST-2 logging in as admin makes the session permanent so the lifetime above applies to it
def test_admin_session_is_permanent(client, admin_user):
    response = client.post("/auth/admin-login", data={
        "username": admin_user["username"],
        "password": admin_user["password"],
    })
    assert response.status_code == 302

    with client.session_transaction() as session:
        assert session.permanent == True
