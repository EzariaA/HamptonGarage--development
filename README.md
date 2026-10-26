# HamptonGarage — Campus Marketplace

**A cloud-based fashion marketplace for Hampton University students**

Designed & Built by David Jackson, Elali McNair, Day Ekoi, Ryan Grimes, Kaila Roberts, and Madison Boyd
CSC 405 — Spring 26'

Adopted by Ezaria Alexander, Ava Bell, Clarence Bostic, Mattie Edoziie, Makens Jelks Mason Johnson, and Kyle Lewis 
CSC 404 - Fall '26
---

## Live Deployment

**http://the-vault-env.eba-a7vun5tm.us-east-2.elasticbeanstalk.com**

---

## What is The Vault?

The Vault is a web-based campus marketplace exclusively for Hampton University students. It allows student brand owners to create storefronts, publish clothing listings, and manage inventory, while other students can browse, wishlist, and purchase items.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| Frontend | HTML, CSS, JavaScript |
| Database | PostgreSQL (AWS RDS) |
| Image Storage | Amazon S3 |
| Cloud Hosting | AWS Elastic Beanstalk |
| DB Adapter | psycopg2 |
| Version Control | GitHub |

---

## Setup & Running Locally

### Prerequisites
- Python 3.10 or newer (3.12 recommended). The built-in Mac Python (3.9) can't install `requirements.txt`; on a Mac run `brew install python@3.12`.
- PostgreSQL running locally (Mac: `brew install postgresql@16 && brew services start postgresql@16`)
- A free [Stripe](https://dashboard.stripe.com/register) account in **test mode** (for checkout)
- AWS credentials are **optional** locally. Without `AWS_S3_BUCKET`, uploaded images are saved to `static/uploads/`.

### Installation

```bash
git clone https://github.com/EzariaA/HamptonGarage--development.git
cd HamptonGarage--development

python3.12 -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

### Create a local database

```bash
createdb thevault
```

Use a **local** database for development. Don't point your `.env` at the shared AWS database.

### Environment Configuration

Create a `.env` file in the project root (it is git-ignored, so never commit it):

```
SECRET_KEY=any-long-random-text
DB_HOST=localhost
DB_PORT=5432
DB_NAME=thevault
DB_USER=your_mac_username
DB_PASSWORD=
DB_SSLMODE=disable

# Stripe test keys: https://dashboard.stripe.com/test/apikeys
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...      # printed by `stripe listen` (see below)

# Optional: S3 image storage
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_S3_BUCKET=
AWS_REGION=us-east-2

# Optional: load the demo storefronts on startup
SEED_DEMO_DATA=true
```

### Initialize the Database

The app creates and updates the tables every time it starts. To do it by hand:

```bash
python backend/init_db.py
```

### Load demo data (optional)

Adds 4 demo storefronts and 12 listings that use the images in `static/images`. It's safe to run again, because existing demo storefronts are skipped.

```bash
python backend/seed_demo_data.py
```

### Run the App

```bash
python app.py
```

Visit `http://127.0.0.1:5000` in your browser.

**Mac users:** if you get "403 Forbidden", AirPlay Receiver is using port 5000. Turn it off in System Settings → General → AirDrop & Handoff, or run `flask --app app run --port 5001 --debug`.

### Stripe payments (checkout)

1. The buyer fills in their details and clicks **Continue to Payment**. The order is saved as `PENDING_PAYMENT`.
2. The buyer pays on Stripe's hosted page. Card details never reach our server.
3. The order is marked `PAID` **only after Stripe confirms**, either through the signed webhook (`POST /api/stripe/webhook`) or when the buyer returns and the server asks Stripe for the session. Inventory, cart and wishlist only update at this point.

To receive webhooks locally, install the [Stripe CLI](https://docs.stripe.com/stripe-cli) and run:

```bash
stripe login
stripe listen --forward-to localhost:5000/api/stripe/webhook
```

Copy the `whsec_...` value it prints into `STRIPE_WEBHOOK_SECRET`. Test card: `4242 4242 4242 4242`, any future date, any CVC.

### Deployment secrets

`.ebextensions/env.config` holds **only non-secret settings**. Set `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `SECRET_KEY`, `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` in the Elastic Beanstalk console under Configuration → Environment properties. On the live site, add a Stripe webhook endpoint at `https://<live-site>/api/stripe/webhook` for the `checkout.session.completed` and `checkout.session.async_payment_succeeded` events.

---

## Running Tests

Unit tests run without a database or internet:

```bash
python -m unittest backend.tests.test_stripe_payment backend.tests.test_env_config backend.tests.test_seed_demo_data -v
```

Full suite (some older tests need the local database from the setup steps above, with at least one user):

```bash
python -m unittest discover -s backend/tests -t . -v
```

---

## Team

| Name | Role |
|---|---|
| David Jackson | Project Manager, Admin backend & frontend |
| Elali McNair | Co-PM, Wishlist & Purchase backend, Create Listing frontend |
| Ryan Grimes | Systems & Security Lead, Auth backend, Login/Signup/Cart frontend |
| Day Ekoi | Cloud Deployment Lead, Storefront & Listings backend & frontend, Returns system, AWS deployment |
| Madison Boyd | Documentation Lead, User & Account Settings backend & frontend |
| Kaila Roberts | Database & App Support, Checkout backend and frontend |

---

## Notes

- Restricted to Hampton University email addresses (`@hamptonu.edu` / `@my.hamptonu.edu`)
- Payments go through Stripe Checkout (test mode); items are still exchanged in person at the buyer's chosen meeting location
- Deployed on AWS Free Tier