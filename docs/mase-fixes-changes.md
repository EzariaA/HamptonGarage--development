# Mase-fixes: What Changed

Branch: `Mase-fixes` · Author: Mason Johnson · Date: 10/26/26

This branch has four changes, a cleanup, and a site-wide visual redesign. Each one is its own commit (the redesign is four commits), so you can look at them one at a time on GitHub.

| # | Change | Commit |
|---|--------|--------|
| 1 | Base template | No change needed (already done in `bdc3e73`) |
| 2 | Pay button + mock card form | `Add Pay button and mock card form to checkout` |
| 3 | Permanently delete a storefront | `Add permanent Delete Storefront with name confirmation` |
| 4 | Sidebar / pagination cleanup | `Remove dead pagination buttons and placeholder sidebar items` |
| 5 | Clear login and signup errors | `Show clear login and signup error messages on the page` |
| 6 | Garage theme redesign (Hampton Garage) | 4 commits starting with `Redesign the homepage with the Hampton Garage garage theme` |

> **Heads up:** change #3 updates the database. The first time you start the app on this branch, `init_db.py` changes the `purchases` table (see below). Nothing else in the schema changes.

---

## 1. Base template

All 17 templates already use `{% extends "base.html" %}` from the earlier base-template merge. I rendered every page to double check: each has one `<!DOCTYPE>`, one `<body>`, and loads `base.css`. **No files changed.**

---

## 2. Pay button and mock card form

**Where:** Checkout page (`/checkout`)

**What happens now:**
1. The buyer fills in their details and clicks **Pay**.
2. A **Card Details** section appears (cardholder name, card number, MM/YY, CVV). The button changes to "Pay $XX.XX".
3. Clicking it again sends the order and card to the server. If the card is wrong, the error shows under that field. If it's right, the order goes through like before and the buyer lands on the order confirmation page.

**Card rules (checked on the server):**
- Card number: 13–19 digits (spaces and dashes are fine) and must pass the Luhn check
- Expiration: `MM/YY`, month 01–12, not in the past (this month is OK)
- CVV: 3 or 4 digits
- Name: can't be empty

**Test cards:** `4242 4242 4242 4242`, any future date like `12/30`, CVV `123`.

**Safety:** No real payment service. The full card number and CVV are **never saved, logged, or shown in errors**. Nothing card-related is stored yet, not even the last 4 digits.

**Files:** `templates/checkout.html`, `static/js/checkout.js`, `static/css/checkout.css`, `backend/controllers/checkout_controller.py`, `backend/services/checkout_service.py`

Not built yet: payment success and cancel pages.

---

## 3. Permanently delete a storefront

**Where:** Edit Storefront page → red **Danger Zone** at the bottom

Deactivate / Reactivate still works exactly the same (it only hides the storefront). Delete is separate and permanent.

**What happens now:**
1. The seller clicks **Delete Storefront**. A box warns that this can't be undone.
2. They must type the storefront name exactly. **Delete Forever** stays greyed out until it matches.
3. The form POSTs to `/storefronts/<id>/delete`. The server checks again:
   - the user is logged in (uses `session['user_id']`, **not** the `X-User-Id` header)
   - the user is the **owner** (admins can't use this; they have their own dashboard tool)
   - the typed name matches
4. On success: redirect to `/storefronts` with a green message. On failure: back to the edit page with a red message, and **nothing is deleted**.

**What happens to linked data:**

| Data | What happens |
|------|-------------|
| Storefront row (logo, banner, preview image URLs) | Deleted |
| Listings, listing images, listing sizes | Deleted |
| Wishlist entries for those listings | Deleted |
| Other users' cart items for those listings | Deleted |
| **Orders / order items** | **Kept** (they save the item name and price) |
| **Purchases** | **Kept** (`listing_id` becomes empty) |
| Returns | Kept |
| Uploaded image files (S3 / `static/uploads`) | Left in storage for now |

Everything is deleted in one transaction: if any step fails, nothing is deleted.

**Database change (`init_db.py`):** `purchases.listing_id` can now be empty, and its foreign key is now `ON DELETE SET NULL` instead of `CASCADE`. This is so deleting a listing no longer wipes purchase records. It runs automatically on startup and is safe to run again.

**Files:** `templates/edit_storefront.html`, `static/js/edit_storefront.js`, `static/css/pages/edit_storefront.css`, `backend/controllers/storefront_controller.py`, `backend/services/storefront_service.py`, `backend/models/storefront_model.py`, `backend/init_db.py`, `templates/storefront.html` + `static/css/storefront.css` (success message)

**Small notes:**
- A buyer who is already logged in may still see a deleted item in their bag until they log in again (the bag is in their session). Checkout blocks it with "no longer available".
- The old `purchases` API (`purchase_model.py`) uses an inner `JOIN`, so purchases with an empty `listing_id` won't show there. The account page uses `orders`, so buyers still see their order history.

---

## 4. Sidebar and pagination cleanup

**Where:** Storefronts page (`/storefronts`)

- Removed the **Previous / Page 1 / Next** buttons. They didn't do anything.
- Removed the commented-out sidebar items that never linked anywhere (Explore Brands, All Categories, New Drops, Hot!, About, Sitemap) and a stray `</div>`.
- Removed unused `.pagination` / `.page-indicator` CSS.

The ☰ sidebar now only has working links: **Create Storefront, Create Listing, My Storefront, Returns**. Pagination can be added back once it's actually built.

**Files:** `templates/storefront.html`, `static/css/storefront.css`

---

## 5. Clear login and signup errors

**Before:** bad logins and signups returned a plain text page, and signing up with an email that was already registered didn't say why it failed.

**Signup now shows, under the right field:**
- Empty fields: "Enter a username." / "Enter your email." / "Enter a password."
- Bad email: "Enter a valid email address, like name@my.hamptonu.edu."
- Not a student email: "You must use your Hampton student email (ending in @my.hamptonu.edu)." *(updated 10/27, see below)*
- Password: at least 8 characters, with a letter and a number
- "That username is already taken."
- **"An account with this email already exists."** (works even if the case is different)

**Login now shows:**
- Empty fields: "Enter your username." / "Enter your password."
- Wrong username or password: **"Incorrect username or password."** (one message on purpose, so we don't reveal which part was wrong)
- Account email isn't a student email: **"Only Hampton student emails (@my.hamptonu.edu) can log in. Please sign up with your student email."** *(added 10/27)*

**Student email rule (updated 10/27):** signing up **and** logging in now require an email whose part after the `@` is exactly `my.hamptonu.edu` (capital letters are fine). The old check only looked at how the email *ended*, so `name@hamptonu.edu` and even `name@fakehamptonu.edu` got through.

| Email | Allowed? |
|-------|----------|
| `jsmith@my.hamptonu.edu` | Yes |
| `jsmith@hamptonu.edu` | No (staff/faculty style, not student) |
| `jsmith@fakemy.hamptonu.edu` | No |
| `jsmith@my.hamptonu.edu.com` | No |

- The check is one function, `is_student_email()` in `backend/services/auth_services.py`, used by signup, `register_user()`, and the login route.
- On login it runs **after** the password is checked, and the user is **not** logged in if it fails.
- **Existing accounts** with a non-student email can no longer log in. My local database had none. **Check the shared AWS database before deploying**: `SELECT username, email FROM users WHERE LOWER(SPLIT_PART(email, '@', 2)) <> 'my.hamptonu.edu';`
- The **admin login** page (`/auth/admin-login`) is separate and doesn't use email, so it's not affected.
- Test scripts `test_register_driver.py` and `test_user.py` now use `@my.hamptonu.edu` emails.

The username and email you typed stay in the form after an error. **Passwords are never refilled.** The login page now also shows "Signup successful!" after you sign up (it was being sent but never displayed).

**Files:** `backend/controllers/auth_controller.py`, `backend/services/auth_services.py`, `templates/login.html`, `templates/signup.html`, `static/css/pages/login.css`, `static/css/pages/signup.css` (10/27: also `backend/tests/test_register_driver.py`, `backend/tests/test_user.py`)

---

## 6. Garage theme redesign (Hampton Garage)

**Why:** the site still looked like "The Vault" (black background, gold, vault wheel). It now matches the Hampton Garage name.

**The new look:**
- A **baby blue banner** with "HAMPTON GARAGE" at the top of every redesigned page (click it to go to the storefronts page; on login/signup it goes to the homepage)
- **Light gray** page background instead of the vault wheel image
- **White cards** with a blue line on top, **navy** text, **faded gray** buttons
- Plain wording instead of vault wording (e.g. "Decrypt Access" → "Log In")

| Commit | Pages |
|--------|-------|
| `Redesign the homepage with the Hampton Garage garage theme` | Homepage: blue banner, open-garage photo, same metal Log In / Sign Up buttons faded to gray. Removed the "V" logo, "Portal to..." text, and fake loading bar. |
| `Restyle login, signup, and admin login with the blue and gray theme` | Login, Signup, Admin Login |
| `Restyle storefront pages with the garage theme and remove The Vault` | Storefronts (top bar is now the blue banner, "Browse Storefronts" heading), Storefront View, My Storefront |
| `Restyle returns and the listing/storefront forms, remove The Vault` | Returns (garage shed photo background), Create/Edit Listing, Create/Edit Storefront |

**Theme colors live in one place:** `static/css/base.css` has them as CSS variables (`--baby-blue`, `--navy`, `--btn-gray`, etc.) plus the shared `.site-banner` class. **To change a color across the site, change it there.** Please use these variables on new pages instead of new hex colors.

**New images:** `static/images/garage.webp` (homepage), `static/images/returns_garage.webp` (returns page)

**Other fixes found while restyling:**
- The browser's "Choose File" button was showing inside every upload box. A shared rule in `static/css/create_storefront.css` was overriding `hidden`. Fixed once there; clicking the box still opens the file picker.
- The side menu divider never showed (`nav-divider` was missing its dot in `storefront.css`).
- Returns: removed the `TheVaultAdmins@my.hamptonu.edu` line. Add a new admin email if the team gets one.

**Kept on purpose:** internal names like `vaultUserId`, `vaultWishlistLocalItems`, `create_vault_tables`, and `VAULT-` order numbers. Renaming the saved-data keys would log everyone out and clear wishlists, and none of them show on screen.

**Also redesigned (10/27):** Account page (the profile icon): blue banner, white card, blue tab underline, gray buttons, red outlined Logout. "SECURED WISHLIST" → "MY WISHLIST", "OPERATOR" → "MY ACCOUNT".

**Not redesigned yet (still dark and gold):** Cart, Checkout, Order Confirmation, Admin Dashboard.

### How the theme code works

You don't need to know all of CSS to work with this. Most of it is three ideas.

**1. Colors are variables in `base.css`**

`base.html` loads `static/css/base.css` on every page, before the page's own CSS. Inside it:

```css
:root {
    --navy: #1c3557;          /* titles and main text */
    --btn-gray: #6b7280;      /* buttons */
    ...
}
```

Each `--name: value` line saves a color under a name. Any CSS file can then use it:

```css
.my-title {
    color: var(--navy);       /* same as color: #1c3557; */
}
```

So if the team wants a different blue, change `--baby-blue` in `base.css` once and every page updates.

| Variable | Used for |
|----------|----------|
| `--baby-blue` / `--baby-blue-dark` | banner, blue line on top of cards, glow around the box you're typing in |
| `--navy` | titles and main text |
| `--page-gray` | page background |
| `--card-white` / `--border-gray` | cards and their borders |
| `--text-gray` | smaller, less important text |
| `--btn-gray` / `--btn-gray-dark` | buttons and their hover color |

**2. The blue banner is one shared class**

`.site-banner` is also in `base.css`. To put the banner on a new page, add this at the top of the page's `{% block content %}`:

```html
<header class="site-banner">
    <a href="/storefronts">HAMPTON GARAGE</a>
</header>
```

No extra CSS needed. (The homepage and the storefronts page have their own bigger versions of the banner, `.top-banner` in `index.css` and `.topbar` in `storefront.css`, because they hold more than just the title.)

**3. Cards, inputs, and buttons follow the same pattern**

When restyling a page, copy these patterns. They're already used on login, storefronts, and the forms:

| Thing | What we use |
|-------|-------------|
| Card / box | `background: var(--card-white);` `border: 1px solid var(--border-gray);` `border-top: 5px solid var(--baby-blue-dark);` `border-radius: 12px;` |
| Input box | `background: #f8fafc;` `border: 1px solid var(--border-gray);` `border-radius: 8px;` `color: var(--navy);` |
| Input you're typing in (`:focus`) | `border-color: var(--baby-blue-dark);` `box-shadow: 0 0 0 3px rgba(167, 211, 242, 0.6);` (the box-shadow draws a soft blue ring) |
| Main button | `background: var(--btn-gray);` `color: white;`, hover: `var(--btn-gray-dark)` |
| Back / cancel button | white background, `border: 1px solid var(--btn-gray);`, fills gray on hover |
| Error message | `background: #fdecec;` `color: #b42318;` (red) |
| Success message | `background: #ecfdf3;` `color: #146c2e;` (green) |

### The trickier lines, explained

Every CSS block has a comment above it. These are the few spots that do something less obvious:

| Where | Line | What it does |
|-------|------|--------------|
| `index.css` `.metallic-btn` | `filter: grayscale(100%) brightness(1.15) opacity(0.85);` | Takes the original gold button picture and removes the color, lightens it a bit, and makes it a little see-through. No new image was needed. |
| `index.css` `.metallic-btn img` | `margin: -15% 0;` | The button pictures have empty space above and below the plate. The negative margin pulls that space in so the box around the buttons isn't too tall. |
| `index.css` `.garage-hero` / `returns.css` `body` | `background: linear-gradient(...), url(...)` | Two background layers: a see-through color on top, the photo underneath. That's what tints the photo. Change the last number in each `rgba(...)` to make the tint lighter (smaller) or darker (bigger). |
| `index.css` `.hero-card` | `backdrop-filter: blur(6px);` | Blurs the photo behind the white box ("frosted glass"). |
| `storefront.css` `.topbar-title` | `position: absolute; left: 50%; transform: translateX(-50%);` | Puts "HAMPTON GARAGE" in the exact middle of the top bar even though the menu button and the icons on each side are different widths. |
| `create_storefront.css` | `input[type="file"][hidden] { display: none; }` | Upload boxes hide the real file input and open it with JavaScript when you click the box. An older rule (`display: block`) was making the browser's "Choose File" button show up anyway. This puts it back to hidden. |
| `returns.css` | `text-shadow: 0 0 12px rgba(255, 255, 255, 0.95)` | A white glow behind the "Returns" title so it's readable on top of the photo. |

**Units you'll see:** `vh` = percent of the screen's height, `vw` = percent of the screen's width (used on the homepage so it scales with the screen). `rem` = based on the normal text size. `@media (max-width: 600px) { ... }` = rules that only apply on phone-sized screens.
> **Heads up for anyone working on checkout** (e.g. the `ezaria-stripe-checkout` branch): this branch did not touch checkout's look, but `base.css` now has the theme variables, so merging should be easy. Use them when restyling.

---

## Things the team should know (not fixed in this branch)

These are outside my tasks, but I found them while working:

1. **Leaked secrets.** `.ebextensions/env.config` still has a real `SECRET_KEY` committed. The first commit also had the AWS database password, which is still in git history. Whoever owns the AWS account should **change the database password and the secret key**, and that file shouldn't hold secrets.
2. **Fakeable ownership check.** The storefront API (`/api/storefronts/...`) decides who you are from an `X-User-Id` header the browser sends, which anyone can change. My delete route uses the session instead. The other routes should be switched too.
3. **Debug route.** `/auth/debug/session` shows the whole session to anyone. It should be removed.
4. **Outdated test.** `backend/tests/test_checkout.py` sends an old request format (`shipping_info`) and expects `201`. It was already failing before this branch.

---

## Running the app locally

1. **Python 3.10 or newer.** The built-in Mac Python (3.9) can't install `requirements.txt`.
   ```bash
   python3.12 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Create a `.env`** in the project folder (it's git-ignored):
   ```
   SECRET_KEY=any-long-random-text
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=your_local_db
   DB_USER=your_mac_username
   DB_PASSWORD=
   DB_SSLMODE=disable
   ```
   Use a **local** Postgres database for testing. Don't point it at the shared AWS database, because testing delete will remove real data.
3. **Run it:** `python app.py`, then open http://127.0.0.1:5000/auth/login
4. **Mac users:** if you see "403 Forbidden", that's AirPlay Receiver using port 5000. Turn it off in System Settings → General → AirDrop & Handoff, or run `flask --app app run --port 5001 --debug` and use port 5001.
