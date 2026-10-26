# Edozie's Changes, Explained Simply

Branch: `edozie-code-contributions` · Author: Mattie Edozie · Date: 10/26/26

This branch does 4 things, plus tests:

| # | What | Points |
|---|------|--------|
| 1 | Real payments with Stripe: an order only counts as **paid** after Stripe says so | 2 |
| 2 | Took the leaked password and secret key out of `.ebextensions/env.config` | 1 |
| 3 | Fixed the README (clone link, setup steps, test command) | 1 |
| 4 | Demo stores and pictures show up on the live site | 1 |
| + | Unit tests for all of the above (39 tests) | |

---

## Words you'll see

| Word | What it means |
|------|---------------|
| **Stripe** | A company that charges credit cards for websites. We never touch card numbers; Stripe does. |
| **Checkout Session** | A payment page Stripe makes for one order. We ask Stripe for one, and it gives us a link. |
| **Webhook** | A message Stripe's computer sends to *our* site when something happens, like "this person paid." |
| **Signature** | A code attached to the webhook that proves it really came from Stripe and wasn't faked. |
| **PENDING_PAYMENT** | The order is saved but **not paid yet**. |
| **PAID** | Stripe confirmed the money went through. |
| **Seed / seeding** | Putting starter (demo) data into the database. |
| **Environment variable** | A setting like a password that lives *outside* the code, in `.env` on your laptop or in AWS settings on the live site. |
| **Unit test** | A small piece of code that checks one function works. Ours don't need a database or internet. |
| **Mock / fake** | In tests, a pretend version of the database or Stripe, so we can test without the real thing. |

---

## 1. Stripe payments

### The problem
Before, clicking **Complete Transaction** saved the order and took the items out of stock right away. Nobody paid anything.

### What happens now

```
Buyer clicks "Continue to Payment"
        |
        v
We save the order as PENDING_PAYMENT          <- items NOT taken out of stock yet
        |
        v
We ask Stripe for a payment page and send the buyer there
        |
        v
Buyer types their card on STRIPE'S page        <- card never touches our site
        |
        v
Stripe tells us "they paid" in one of 2 ways:
   (a) Webhook: Stripe's computer messages /api/stripe/webhook
   (b) Return:  buyer lands on the confirmation page, and we ask Stripe "did they pay?"
        |
        v
We double check 3 things:
   1. Stripe says payment_status is "paid"
   2. It's the payment page we made for THIS order
   3. The amount paid matches the order total
        |
        v
Order becomes PAID -> NOW we take items out of stock, empty the cart and wishlist
```

**Why two ways?** The webhook is the reliable one: it works even if the buyer closes the tab. The return check means the buyer sees "Payment Confirmed" right away instead of waiting.

**What if both happen?** Only the first one counts. `mark_order_paid` only changes an order that is still `PENDING_PAYMENT`, so stock is never taken out twice.

**What if the buyer hits "back" on Stripe?** They go back to checkout with a message saying the payment was canceled. The order stays unpaid and nothing comes out of stock.

**What if Stripe isn't set up (no key)?** Checkout says "Online payments are not set up yet" and doesn't save an order.

### Files changed

| File | What I did |
|------|------------|
| `backend/services/payment_service.py` | **New.** All the Stripe code lives here. Read this one first; every step has a comment. |
| `backend/controllers/checkout_controller.py` | The `/checkout/complete` route now sends back Stripe's link. I added two routes: `/stripe/webhook` and `/checkout/confirm`. |
| `backend/services/checkout_service.py` | Split the old function in two: `create_pending_order` (saves the order) and `fulfill_paid_order` (stock, cart, wishlist, run only after payment). |
| `backend/models/checkout_model.py` | 3 small database functions: `get_order_by_id`, `set_order_stripe_session`, `mark_order_paid`. |
| `backend/init_db.py` | Adds 2 columns to `orders`: `stripe_session_id` and `paid_at`. Runs automatically on startup. |
| `static/js/checkout.js` | After the order is saved, sends the buyer to Stripe's link. Shows a message if they canceled. |
| `templates/checkout.html` | Button now says **Continue to Payment**. |
| `templates/order_confirmation.html` | When the buyer comes back from Stripe, it asks our server to check the payment first. Shows **Payment Confirmed** or **Payment Processing**. |
| `requirements.txt` | Added `stripe`, Stripe's official Python library. |

---

## 2. Leaked secrets

### The problem
`.ebextensions/env.config` is on GitHub, so anyone who can see the repo can read it. It had the real `SECRET_KEY`, which is used to sign login sessions. An older version also had the real database password.

### What I did
- Removed every secret from the file. Now it only has safe settings: the S3 bucket name, the region, and `SEED_DEMO_DATA`.
- Added a comment at the top saying where secrets go instead: the AWS Elastic Beanstalk settings page.
- Added a test (`test_env_config.py`) that fails if anyone puts a secret back in.

### ⚠️ Still needs doing (by whoever owns the AWS account)
Deleting a secret from the file **doesn't erase it from git history**, so anyone can still find the old values. The database password and secret key need to be **changed** in AWS. After that, the old ones are useless.

---

## 3. README

- The clone link now points to our repo (`EzariaA/HamptonGarage--development`).
- Setup steps now say you need Python 3.10+ (the Mac's built-in 3.9 doesn't work), explain how to make a local database, and show what goes in `.env`.
- New sections: setting up Stripe, where deployment secrets go, and loading demo data.
- The test command now actually works (the old one was `python3 backend/tests/test_file_name`).

---

## 4. Demo data on the live site

### The problem
The live site was empty, and pictures uploaded on someone's laptop don't exist on AWS.

### What I did
- **New file `backend/seed_demo_data.py`.** It makes 4 demo stores (Nike, Essentials, Von Dutch, Onyx) with 12 listings. Every listing has sizes S/M/L/XL in stock.
- The pictures are the files already in `static/images`. Those get uploaded to AWS with the rest of the code, so they work on the live site.
- **It's safe to run again and again.** If a demo store already exists, it's skipped.
- Each demo store has its own owner account with a random password nobody knows, so nobody can log in as a demo owner.
- `app.py` runs it every time the app starts **if** `SEED_DEMO_DATA` is `true`. The live site has that turned on in `env.config`, so the next deploy loads the demo stores.

To run it by hand on your laptop:
```bash
python backend/seed_demo_data.py
```

---

## Tests

3 new test files, 39 tests total. They don't need a database or internet.

| File | What it checks |
|------|----------------|
| `backend/tests/test_stripe_payment.py` | An order is only marked paid when Stripe says paid, it's the right order and it's the right amount. It's never processed twice. Fake webhooks are rejected and real ones are accepted. Nothing comes out of stock before payment. The routes return the right responses. |
| `backend/tests/test_env_config.py` | No passwords or keys in `env.config`. |
| `backend/tests/test_seed_demo_data.py` | Demo data creates 4 stores, running it twice adds nothing, passwords are hashed, every listing has 1 main picture, an error undoes everything, and every picture file exists. |

Run them:
```bash
python -m unittest backend.tests.test_stripe_payment backend.tests.test_env_config backend.tests.test_seed_demo_data -v
```

I also ran the payment flow and the demo loader against a real local Postgres database to make sure the SQL works.

---

## How to try Stripe on your laptop

1. Make a free Stripe account and stay in **Test mode**. Copy your test secret key (starts with `sk_test_`) from https://dashboard.stripe.com/test/apikeys
2. Put it in your `.env`: `STRIPE_SECRET_KEY=sk_test_...`
3. Install the Stripe CLI (`brew install stripe/stripe-cli/stripe`), then run:
   ```bash
   stripe login
   stripe listen --forward-to localhost:5000/api/stripe/webhook
   ```
   It prints a secret that starts with `whsec_`. Put it in `.env` as `STRIPE_WEBHOOK_SECRET=whsec_...`
4. Run the app, add something to your cart, and check out.
5. On Stripe's page use the test card **4242 4242 4242 4242**, any future date (like 12/30), and any CVC (like 123).
6. You land on the confirmation page with **Payment Confirmed**, and the status says `PAID`.

No real money moves in test mode.

---

## What the team needs to do for the live site

1. **Change the database password and `SECRET_KEY`** in AWS (see section 2).
2. In AWS Elastic Beanstalk → Configuration → Environment properties, add:
   - `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `SECRET_KEY`
   - `STRIPE_SECRET_KEY` (the `sk_test_...` key)
   - `STRIPE_WEBHOOK_SECRET` (from step 3)
3. In the Stripe dashboard → Developers → Webhooks, add an endpoint at `http://<live-site-address>/api/stripe/webhook` and choose these 2 events:
   - `checkout.session.completed`
   - `checkout.session.async_payment_succeeded`

   Copy its signing secret (`whsec_...`) into `STRIPE_WEBHOOK_SECRET`.

## Heads up: overlap with Mase-fixes

Mason's `Mase-fixes` branch adds a pretend card form to checkout, and it changes the same checkout files as this branch. Whichever branch is merged second will need its conflicts fixed. Since Stripe's page now takes the card, we won't need the pretend form once this is merged.
