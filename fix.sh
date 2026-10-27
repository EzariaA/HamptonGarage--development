cat > backend/controllers/checkout_controller.py <<'HG_EOF'
# Hampton Garage
# CSC 404 FALL 26'
# Updated by Ezaria Alexander - Stripe Checkout (create-session / success)
# 10/27/26 - Team decision: Ezaria's Stripe flow is the only checkout flow.
#   Mattie's alternate payment routes and Mason's mock card check were removed
#   after the merge, to keep checkout simple.
#
# How checkout works:
#   1. checkout.js sends the buyer's details to /api/checkout/create-session
#   2. We check stock and prices (from the database), then ask Stripe for a payment page
#   3. The buyer pays on Stripe's page (we never see the card)
#   4. Stripe sends the buyer to /api/checkout/success; we confirm with Stripe that it was paid,
#      and only then create the order, update stock, and empty the cart

import os

import stripe
from flask import Blueprint, request, jsonify, session, redirect

from db import get_connection
from models.listing_model import get_listing_by_id
from models.checkout_model import check_listing_availability
from services.checkout_service import (
    complete_transaction_from_session,
    get_order_summary_service,
    get_user_orders_service,
)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
REQUIRED_FIELDS = ["first_name", "last_name", "email", "contact", "meeting_location"]

checkout_bp = Blueprint("checkout", __name__)


@checkout_bp.route("/orders/by-confirmation/<confirmation_number>", methods=["GET"])
def get_order_confirmation(confirmation_number):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    try:
        result = get_order_summary_service(confirmation_number, user_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@checkout_bp.route("/orders/my", methods=["GET"])
def get_my_orders():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    try:
        orders = get_user_orders_service(user_id)
        return jsonify({"orders": orders}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@checkout_bp.route("/checkout/create-session", methods=["POST"])
def create_checkout_session():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401
    cart = session.get("cart", [])
    if not cart:
        return jsonify({"error": "Cart is empty"}), 400

    data = request.get_json() or {}
    buyer = {f: (data.get(f) or "").strip() for f in REQUIRED_FIELDS}
    if not all(buyer.values()):
        return jsonify({"error": "Please fill in all fields."}), 400

    try:
        line_items = []
        for item in cart:
            listing_id = int(item["id"])
            qty = int(item.get("quantity", 1))
            check_listing_availability(listing_id, qty)
            listing = get_listing_by_id(listing_id)
            if not listing:
                return jsonify({"error": "An item in your cart is no longer available."}), 400
            line_items.append({
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": item.get("name") or "Item"},
                    # Price comes from the database, not the cart, so it can't be changed by the buyer
                    "unit_amount": int(round(float(listing["price"]) * 100)),
                },
                "quantity": qty,
            })

        stripe_session = stripe.checkout.Session.create(
            mode="payment",
            line_items=line_items,
            customer_email=buyer["email"],
            success_url=request.host_url + "api/checkout/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.host_url + "checkout",
            metadata={"user_id": str(user_id)},
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    session["pending_buyer"] = buyer
    return jsonify({"url": stripe_session.url})


@checkout_bp.route("/checkout/success")
def checkout_success():
    session_id = request.args.get("session_id")
    user_id = session.get("user_id")
    if not session_id or not user_id:
        return redirect("/checkout")

    conn = get_connection()
    cur = conn.cursor()
    try:
        # Page refreshed? The order already exists, so don't create it twice.
        cur.execute("SELECT confirmation_number FROM orders WHERE stripe_session_id = %s", (session_id,))
        row = cur.fetchone()
        if row:
            return redirect(f"/order-confirmation?conf={row[0]}")

        # Ask Stripe directly whether this session was paid, and by this user
        stripe_session = stripe.checkout.Session.retrieve(session_id)
        if stripe_session.payment_status != "paid" or stripe_session.metadata.to_dict().get("user_id") != str(user_id):
            return redirect("/checkout")

        buyer = session.pop("pending_buyer", {})
        result = complete_transaction_from_session(user_id, session.get("cart", []), buyer)
        cur.execute(
            "UPDATE orders SET stripe_session_id = %s, payment_status = 'paid' WHERE confirmation_number = %s",
            (session_id, result["confirmation_number"]),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    session["cart"] = []
    session.modified = True
    return redirect(f"/order-confirmation?conf={result['confirmation_number']}")
HG_EOF
cat > .ebextensions/env.config <<'HG_EOF'
# Secrets (DB_PASSWORD, SECRET_KEY, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, ...) do NOT go in this file.
# Set them in the Elastic Beanstalk console: Configuration > Updates, monitoring, and logging > Environment properties.
# Updated by Mattie Edozie 10/26/26
# 10/27/26: DB_NAME, DB_PORT and DB_SSLMODE restored (lost in the merge); SEED_DEMO_DATA added (expected by test_env_config.py)
option_settings:
  aws:elasticbeanstalk:application:environment:
    AWS_REGION: us-east-2
    DB_NAME: thevault
    DB_PORT: "5432"
    DB_SSLMODE: require
    SEED_DEMO_DATA: "true"
HG_EOF
cat > vault-on.sh <<'HG_EOF'
#!/usr/bin/env bash
# Turns the live site back ON. Run with: bash vault-on.sh

# Start the database and wait until it's ready
aws rds start-db-instance --db-instance-identifier hamptongarage-db > /dev/null
aws rds wait db-instance-available --db-instance-identifier hamptongarage-db

# Turn the app server back on (1 server)
ASG=$(aws elasticbeanstalk describe-environment-resources --environment-name hamptongarage-env --query "EnvironmentResources.AutoScalingGroups[0].Name" --output text)
aws autoscaling update-auto-scaling-group --auto-scaling-group-name "$ASG" --min-size 1 --max-size 1 --desired-capacity 1
echo "Server starting. Run 'eb status' in about 5 minutes and look for Green."
HG_EOF
cat > vault-off.sh <<'HG_EOF'
#!/usr/bin/env bash
# Turns the live site OFF to save AWS credits. Run with: bash vault-off.sh

# Find the Auto Scaling group that runs our app server
ASG=$(aws elasticbeanstalk describe-environment-resources --environment-name hamptongarage-env --query "EnvironmentResources.AutoScalingGroups[0].Name" --output text)

# Turn off the app server (0 servers)
aws autoscaling update-auto-scaling-group --auto-scaling-group-name "$ASG" --min-size 0 --max-size 0 --desired-capacity 0

# Stop the database
aws rds stop-db-instance --db-instance-identifier hamptongarage-db > /dev/null
echo "Turning off. Wait 5-10 minutes before running vault-on.sh."
HG_EOF
cat > vault-on.ps1 <<'HG_EOF'
# Turns the live site back ON. Run with: .\vault-on.ps1

# Start the database and wait until it's ready
aws rds start-db-instance --db-instance-identifier hamptongarage-db | Out-Null
aws rds wait db-instance-available --db-instance-identifier hamptongarage-db

# Turn the app server back on (1 server)
$asg = aws elasticbeanstalk describe-environment-resources --environment-name hamptongarage-env --query "EnvironmentResources.AutoScalingGroups[0].Name" --output text
aws autoscaling update-auto-scaling-group --auto-scaling-group-name $asg --min-size 1 --max-size 1 --desired-capacity 1
Write-Host "Server starting. Run 'eb status' in about 5 minutes and look for Green."
HG_EOF
cat > vault-off.ps1 <<'HG_EOF'
# Turns the live site OFF to save AWS credits. Run with: .\vault-off.ps1

# Find the Auto Scaling group that runs our app server
$asg = aws elasticbeanstalk describe-environment-resources --environment-name hamptongarage-env --query "EnvironmentResources.AutoScalingGroups[0].Name" --output text

# Turn off the app server (0 servers)
aws autoscaling update-auto-scaling-group --auto-scaling-group-name $asg --min-size 0 --max-size 0 --desired-capacity 0

# Stop the database
aws rds stop-db-instance --db-instance-identifier hamptongarage-db | Out-Null
Write-Host "Turning off. Wait 5-10 minutes before running vault-on.ps1."
HG_EOF
python3 - <<'HG_PY'
def cut(p, start, end=None, keep_end=True):
    s = open(p).read()
    a = s.index(start)
    if end is None:
        s = s[:a].rstrip() + "\n"
    else:
        b = s.index(end, a)
        s = s[:a] + s[b:]
    open(p, "w").write(s)
sv = "backend/services/checkout_service.py"
cut(sv, "# ________________________________________________________\n# MOCK CARD PAYMENT CHECKS", "def complete_transaction_from_session(")
cut(sv, "def fulfill_paid_order(", "def get_order_summary_service(")
cut("backend/models/checkout_model.py", "# ________________________________________________________\n# STRIPE PAYMENT HELPERS")
cut("static/css/checkout.css", "/* Mock card form - Added by Mason Johnson 10/26/26 */")
cut("templates/order_confirmation.html", "        // Coming back from Stripe: ask the server", "        let order, orderItems;")
p = "templates/checkout.html"; s = open(p).read()
a = s.index("                <!-- Mock card form"); b = s.index("            </form>", a)
s = s[:a].rstrip(" \n") + "\n" + s[b:]
s = s.replace("Updated by Mason Johnson 10/26/26 - added Pay button and mock card form\n", "Updated by Mason Johnson 10/26/26 - added Pay button\n10/27/26 - mock card form removed; buyers enter their card on Stripe's page (Ezaria's flow)\n")
s = s.replace("            <!-- Pay button: first click shows the card form, second click submits the payment -->\n", "            <!-- Pay button: sends the buyer details, then goes to Stripe's payment page -->\n")
open(p, "w").write(s)
p = "static/js/checkout.js"; s = open(p).read()
a = s.index("    // Stripe sends the buyer back here with ?canceled=1"); b = s.index("    // Load cart from Flask session", a); s = s[:a] + s[b:]
a = s.index("    // Mock card form - Added by Mason Johnson 10/26/26"); b = s.index("    // Handle form submission", a)
s = s[:a] + "    const payLabel = `Pay $${total.toFixed(2)}`;\n    if (submitBtn) submitBtn.textContent = payLabel;\n\n" + s[b:]
a = s.index("        // Step 1: buyer details are filled in"); b = s.index("        if (submitBtn) {\n            submitBtn.disabled = true;\n            submitBtn.textContent = \"Processing...\"", a); s = s[:a] + s[b:]
a = s.index("                    card: {"); b = s.index("                }),", a); s = s[:a] + s[b:]
s = s.replace('            if (!res.ok) {\n                if (data.card_errors) showCardErrors(data.card_errors);\n                throw new Error(data.error || "Transaction failed.");\n            }', '            if (!res.ok) throw new Error(data.error || "Transaction failed.");')
s = s.replace("""    - Submits buyer details to /api/checkout/complete
    - Redirects to order confirmation on success
    Updated by Mason Johnson - 10/26/26
    - Pay button shows the mock card form, then sends the card with the order
    - Shows card errors from the server next to the matching field
*/""", """    - Submits buyer details to /api/checkout/create-session (Ezaria's Stripe flow)
    - Sends the buyer to Stripe's payment page; Stripe returns them to the order confirmation
    Updated by Mason Johnson - 10/26/26 - Pay button
    10/27/26 - mock card form removed; the card is entered on Stripe's page only
*/""")
s = s.replace("    // Handle form submission: first Pay click opens the card form, the next one sends the payment\n", "    // Handle form submission: send buyer details, then go to Stripe's payment page\n")
open(p, "w").write(s)
print("Done: checkout files updated.")
HG_PY