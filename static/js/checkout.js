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

            const row = document.createElement("div");
            row.style.cssText = "display:flex; justify-content:space-between; margin-bottom:10px; border-bottom:1px solid rgba(184,134,11,0.2); padding-bottom:8px;";
            row.innerHTML = `
                <div>
                    <div style="font-weight:bold; color:#f0f0f0;">${item.name || "Item"}</div>
                    <div style="color:#888; font-size:0.82rem; margin-top:2px;">
                        ${item.size ? `Size: ${item.size} &nbsp;|&nbsp; ` : ""}Qty: ${qty}
                    </div>
                </div>
                <span class="gold" style="white-space:nowrap; align-self:center;">$${subtotal.toFixed(2)}</span>
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
            const res = await fetch("/api/checkout/complete", {
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

            window.location.href = `/order-confirmation?conf=${encodeURIComponent(data.confirmation_number)}`;
        } catch (err) {
            showError(err.message || "Something went wrong. Please try again.");
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = payLabel;
            }
        }
    });
});
