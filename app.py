import sys
import os
import logging
from dotenv import load_dotenv  # added - ava
from datetime import timedelta # added - Makena Jelks

load_dotenv()  # added - ava: read settings from .env

# added - Makena Jelks (lines 10 - 13) one logging setup for app
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from flask import Flask, render_template, redirect, url_for, session

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend'))) # Updated 3/19/2026 by Ryan Grimes

from controllers.listing_controller import listing_bp
from controllers.storefront_controller import storefront_bp, storefront_pages_bp  # Updated by Day E 3/22/26
from controllers.purchase_controller import purchase_bp
from controllers.wishlist_controller import wishlist_bp
from controllers.admin_controller import admin_bp
from controllers.auth_controller import auth_bp # Updated 3/19/2026 by Ryan Grimes
from controllers.return_controller import returns_bp
from controllers.checkout_controller import checkout_bp
from init_db import create_vault_tables


def create_app():
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    # added - ava: get the secret key from .env
    app.secret_key = os.getenv("SECRET_KEY")

    # added - ava: stop if the secret key is missing
    if not app.secret_key:
        raise RuntimeError("Add SECRET_KEY to your .env file")

    # added - Makena Jelks: permanent admin sessions expire after 30 min
    app.permanent_session_lifetime = timedelta(minutes=30)

    # Run DB migrations on every startup so new columns are always present
    try:
        from init_db import create_vault_tables
        create_vault_tables()
    except Exception as _db_init_err:
        # added - ava: record the warning using Flask logging
        app.logger.warning("DB migration failed: %s", _db_init_err)

    # Load demo storefronts and listings when SEED_DEMO_DATA=true (the live site sets this in .ebextensions/env.config)
    # Added by Mattie Edozie 10/26/26
    if os.getenv("SEED_DEMO_DATA", "").lower() == "true":
        try:
            from seed_demo_data import seed_demo_data
            created = seed_demo_data()
            app.logger.info("Demo data: %s new storefront(s) created", created)
        except Exception as _seed_err:
            app.logger.warning("Demo data load failed: %s", _seed_err)
    #The Welcome Screen (Default) Ryan Grimes 3/19/2026
    @app.route('/')
    def index():
        return render_template('index.html')

    # Route to the main storefront page after login - Updated 3/22/2026
    @app.route('/storefront')
    def storefront():
        return render_template('storefront.html')

    # Route to the "Create Storefront" form - Updated 3/22/2026
    @app.route('/create-storefront')
    def create_storefront():
        return render_template('create_storefront.html')

    # Route to the "Create Listing" form - Updated 3/24/2026
    @app.route('/create-listing')
    def create_listing():
        return render_template('create_listing.html')

    #Route to the Cart screen - Updated 3/22/2026
    @app.route('/cart')
    def cart():
        return render_template('cart.html')

    #Route to the Checkout - Updated 4/22/2026
    @app.route('/checkout')
    def checkout():
        if not session.get("user"):
            return redirect(url_for("auth.login"))
        return render_template('checkout.html')

    # Route to the Order Confirmation page - Added 4/22/2026
    @app.route('/order-confirmation')
    def order_confirmation():
        if not session.get("user"):
            return redirect(url_for("auth.login"))
        return render_template('order_confirmation.html')
    
    # Route to My Storefront dashboard page - Updated 4/9/2026
    @app.route('/my-storefront')
    def my_storefront():
        if not session.get("user"):
            return redirect(url_for("auth.login"))
        return render_template('my_storefront.html')

    # Customer browse pages - Added by Clarence Bostic - Iteration 3
    @app.route('/recent-listings')
    def recent_listings():
        return render_template('recent_listings.html')

    @app.route('/categories')
    def categories():
        return render_template('categories.html')

    # Register Blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(listing_bp)
    app.register_blueprint(storefront_bp)
    app.register_blueprint(storefront_pages_bp)  # Updated by Day E 3/22/26
    app.register_blueprint(purchase_bp)
    app.register_blueprint(wishlist_bp)
    app.register_blueprint(admin_bp) # Updated 3/19/2026 by Ryan Grimes
    app.register_blueprint(returns_bp)
    app.register_blueprint(checkout_bp, url_prefix='/api')

    # added (line 129-136) - Makena Jelks
    @app.errorhandler(404)
    def page_not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        app.logger.error("500 error: %s", getattr(error, "original_exception", error))
        return render_template("errors/500.html"), 500

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
