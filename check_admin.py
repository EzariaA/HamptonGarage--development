import sys
import secrets
from unittest.mock import MagicMock, patch
from flask import Flask

sys.path.insert(0, "backend")
from controllers import auth_controller
from utils.auth_utils import hash_password

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config["TESTING"] = True
app.register_blueprint(auth_controller.auth_bp, url_prefix="/auth")
app.add_url_rule(
    "/admin", endpoint="admin.admin_dashboard",
    view_func=lambda: "Admin dashboard"
)

password = secrets.token_hex(16)
hashed = hash_password(password)

for role, pw, allowed in [
    ("admin", "wrong-password", False),
    ("user", password, False),
    ("admin", password, True),
]:
    conn = MagicMock()
    conn.cursor.return_value.fetchone.side_effect = [(hashed, role), (42,)]
    with patch.object(auth_controller, "get_connection", return_value=conn):
        with app.test_client() as client:
            response = client.post("/auth/admin-login", data={
                "username": "test-account", "password": pw
            })
            with client.session_transaction() as session:
                if allowed:
                    assert response.status_code == 302
                    assert response.headers["Location"] == "/admin"
                    assert session["role"] == "admin"
                    assert session["user_id"] == 42
                else:
                    assert b"Invalid Admin Credentials" in response.data
                    assert "user" not in session
            conn.close.assert_called_once()
    print("PASS:", role, "accepted" if allowed else "rejected")

with app.test_client() as client:
    assert client.get("/auth/debug/session").status_code == 404

print("PASS: Debug session route removed")
print("All simulated admin login checks passed.")