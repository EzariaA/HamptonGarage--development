/*
    checkout.js
    The Vault Campus Marketplace
    CSC 405 Sp 26'
    Updated by Day Ekoi - 4/22/26
    - Reads cart from session via /auth/cart/json
    - Displays items with size, qty, and subtotals
    - Submits buyer details to /api/checkout/complete
    - Redirects to order confirmation on success
    Updated by Mason Johnson - 10/26/26
    - Pay button shows the mock card form, then sends the card with the order
    - Shows card errors from the server next to the matching field
*/

document.addEventListener("DOMContentLoaded", async () => {
    const itemsList = document.getElementById("checkoutItemsList");
    const totalDisplay = document.querySelector(".total-amount");
    const submitBtn = document.getElementById("submitCheckoutBtn");
    const errorMsg = document.getElementById("checkoutError");

    function showError(msg) {
        if (!errorMsg) return;
        errorMsg.textContent = msg;
        errorMsg.style.display = "block";
        errorMsg.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function hideError() {
        if (errorMsg) errorMsg.style.display = "none";
    }

    // Stripe sends the buyer back here with ?canceled=1 if they leave the payment page
    if (new URLSearchParams(window.location.search).get("canceled")) {
        showError("Payment was canceled. Your order has not been paid. You can try again below.");
    }

    // Load cart from Flask session
    let cart = [];
    try {
        const res = await fetch("/auth/cart/json");
        if (res.ok) cart = await res.json();
    } catch (e) {
        console.error("Failed to load cart:", e);
    }

    if (!Array.isArray(cart) || cart.length === 0) {
        if (itemsList) itemsList.innerHTML = '<p class="helper-text">Your bag is currently empty.</p>';
        if (totalDisplay) totalDisplay.textContent = "$0.00";
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = "Cart is Empty";
        }
        return;
    }

    // Render cart items in order summary
    let total = 0;
    if (itemsList) {
        itemsList.innerHTML = "";
        cart.forEach((item) => {
            const price = parseFloat(item.price || 0);
            const qty = parseInt(item.quantity || 1, 10);
            const subtotal = price * qty;
            total += subtotal;

            // One row per item. The look comes from checkout.css
            // (inline colors swapped for classes by Mason Johnson 11/12/26 for the garage theme)
            const row = document.createElement("div");
            row.className = "checkout-item";
            row.innerHTML = `
                <div>
                    <div class="checkout-item-name">${item.name || "Item"}</div>
                    <div class="checkout-item-meta">
                        ${item.size ? `Size: ${item.size} &nbsp;|&nbsp; ` : ""}Qty: ${qty}
                    </div>
                </div>
                <span class="checkout-item-price">$${subtotal.toFixed(2)}</span>
            `;
            itemsList.appendChild(row);
        });
    }

    if (totalDisplay) totalDisplay.textContent = `$${total.toFixed(2)}`;

    // Mock card form - Added by Mason Johnson 10/26/26
    // Maps each card field name from the server to its input and error line on the page
    const cardSection = document.getElementById("cardSection");
    const cardFields = {
        name: { input: document.getElementById("cardName"), error: document.getElementById("cardNameError") },
        number: { input: document.getElementById("cardNumber"), error: document.getElementById("cardNumberError") },
        expiry: { input: document.getElementById("cardExpiry"), error: document.getElementById("cardExpiryError") },
        cvv: { input: document.getElementById("cardCvv"), error: document.getElementById("cardCvvError") },
    };
    const payLabel = `Pay $${total.toFixed(2)}`;

    // Clears all card error messages and red borders
    function clearCardErrors() {
        for (const field in cardFields) {
            cardFields[field].error.textContent = "";
            cardFields[field].input.classList.remove("input-invalid");
        }
    }

    // Puts each error message under the card field it belongs to
    function showCardErrors(errors) {
        for (const field in errors) {
            if (cardFields[field]) {
                cardFields[field].error.textContent = errors[field];
                cardFields[field].input.classList.add("input-invalid");
            }
        }
    }

    // Handle form submission: first Pay click opens the card form, the next one sends the payment
    const form = document.getElementById("checkoutForm");
    if (!form) return;

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        hideError();

        const firstName = (document.getElementById("firstName")?.value || "").trim();
        const lastName = (document.getElementById("lastName")?.value || "").trim();
        const email = (document.getElementById("buyerEmail")?.value || "").trim();
        const contact = (document.getElementById("contactNumber")?.value || "").trim();
        const meetingLocation = (document.getElementById("meetingLocation")?.value || "").trim();

        if (!firstName || !lastName || !email || !contact || !meetingLocation) {
            showError("All fields are required to complete your transaction.");
            return;
        }

        // Step 1: buyer details are filled in, so show the card form
        if (cardSection.style.display === "none") {
            cardSection.style.display = "block";
            if (submitBtn) submitBtn.textContent = payLabel;
            cardFields.name.input.focus();
            return;
        }

        // Step 2: send the order with the card info
        clearCardErrors();

        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = "Processing...";
        }

        try {
            const res = await fetch("/api/checkout/create-session", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    first_name: firstName,
                    last_name: lastName,
                    email,
                    contact,
                    meeting_location: meetingLocation,
                    card: {
                        name: cardFields.name.input.value,
                        number: cardFields.number.input.value,
                        expiry: cardFields.expiry.input.value,
                        cvv: cardFields.cvv.input.value,
                    },
                }),
            });

            const data = await res.json();

            if (!res.ok) {
                if (data.card_errors) showCardErrors(data.card_errors);
                throw new Error(data.error || "Transaction failed.");
            }

            window.location.href = data.url;
        } catch (err) {
            showError(err.message || "Something went wrong. Please try again.");
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = payLabel;
            }
        }
    });
        // Message when the buyer comes back from Stripe without a finished order
        const returnParams = new URLSearchParams(window.location.search);
        const returnStatus = returnParams.get("status");
        if (returnStatus === "cancelled") 
        {
            showError("Payment cancelled. Nothing was charged and your cart is still here. You can try again when you're ready.");
        } 
        else if (returnStatus === "order_failed") 
        {
            const rawRef = returnParams.get("ref") || "";
            const ref = /^cs_[A-Za-z0-9_]+$/.test(rawRef) ? rawRef : "not available";
            showError("Your payment went through, but we couldn't finish your order. Please don't pay again. Send us this reference and we'll sort it out: " + ref);
        }
});
