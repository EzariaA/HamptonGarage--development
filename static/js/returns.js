/*
    returns.js

    Handles return form interactions and submission.
*/

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("returnsForm");
    const cancelBtn = document.getElementById("cancelBtn");
    const backBtn = document.getElementById("backBtn");
    const damageZone = document.getElementById("damageZone");
    const damageInput = document.getElementById("damageImage");
    const damagePreview = document.getElementById("damagePreview");
    const feedback = document.getElementById("returnsFeedback");

    function showFeedback(message, tone = "success") {
        if (!feedback) return;
        feedback.textContent = message;
        feedback.classList.toggle("error", tone === "error");
        feedback.style.display = "block";
    }

    function clearFeedback() {
        if (!feedback) return;
        feedback.textContent = "";
        feedback.classList.remove("error");
        feedback.style.display = "none";
    }

    function showPreview(file) {
        if (!damagePreview) return;
        damagePreview.innerHTML = "";
        if (!file) return;

        const wrap = document.createElement("div");
        wrap.className = "thumb-wrap";

        const img = document.createElement("img");
        img.src = URL.createObjectURL(file);
        img.alt = file.name;
        img.onload = () => URL.revokeObjectURL(img.src);

        const name = document.createElement("span");
        name.className = "thumb-name";
        name.textContent = file.name;

        wrap.appendChild(img);
        wrap.appendChild(name);
        damagePreview.appendChild(wrap);
    }

    function wireDamageZone() {
        if (!damageZone || !damageInput) return;

        damageZone.addEventListener("click", () => damageInput.click());

        damageZone.addEventListener("dragover", (event) => {
            event.preventDefault();
            damageZone.classList.add("dragover");
        });

        damageZone.addEventListener("dragleave", () => {
            damageZone.classList.remove("dragover");
        });

        damageZone.addEventListener("drop", (event) => {
            event.preventDefault();
            damageZone.classList.remove("dragover");

            const file = event.dataTransfer?.files?.[0];
            if (!file || !file.type.startsWith("image/")) return;

            const transfer = new DataTransfer();
            transfer.items.add(file);
            damageInput.files = transfer.files;
            showPreview(file);
        });

        damageInput.addEventListener("change", () => {
            showPreview(damageInput.files?.[0] || null);
        });
    }

    wireDamageZone();

    // HG-119 (Mattie Edozie, I4): "My Returns" list with loading and empty states.
    // Text is set with textContent so user-typed reasons cannot inject HTML.
    const myReturnsStatus = document.getElementById("myReturnsStatus");
    const myReturnsList = document.getElementById("myReturnsList");

    function setReturnsStatus(message, isError = false) {
        if (!myReturnsStatus) return;
        myReturnsStatus.textContent = message;
        myReturnsStatus.classList.toggle("error", isError);
        myReturnsStatus.style.display = message ? "block" : "none";
    }

    function renderReturn(item) {
        const li = document.createElement("li");
        li.className = "my-return-item";

        const top = document.createElement("div");
        top.className = "my-return-top";

        const order = document.createElement("span");
        order.className = "my-return-order";
        order.textContent = `Order ${item.order_number}`;

        const status = document.createElement("span");
        status.className = `my-return-status status-${item.status}`;
        status.textContent = item.status;

        top.appendChild(order);
        top.appendChild(status);

        const reason = document.createElement("p");
        reason.className = "my-return-reason";
        reason.textContent = item.reason;

        const meta = document.createElement("p");
        meta.className = "my-return-meta";
        const date = item.created_at ? new Date(item.created_at).toLocaleDateString() : "";
        meta.textContent = `${date}${item.has_damage ? " · Damage reported" : ""}`;

        li.appendChild(top);
        li.appendChild(reason);
        li.appendChild(meta);
        return li;
    }

    async function loadMyReturns() {
        if (!myReturnsList) return;
        myReturnsList.innerHTML = "";
        setReturnsStatus("Loading your returns...");

        try {
            const response = await fetch("/returns/my");
            if (response.status === 401) {
                window.location.href = "/auth/login";
                return;
            }
            if (!response.ok) throw new Error();

            const returns = await response.json();
            if (returns.length === 0) {
                setReturnsStatus("No returns yet.");
                return;
            }

            setReturnsStatus("");
            returns.forEach((item) => myReturnsList.appendChild(renderReturn(item)));
        } catch (error) {
            setReturnsStatus("Could not load your returns. Please refresh the page.", true);
        }
    }

    loadMyReturns();

    if (cancelBtn) {
        cancelBtn.addEventListener("click", () => {
            window.location.href = "/storefronts";
        });
    }

    if (backBtn) {
        backBtn.addEventListener("click", () => {
            window.location.href = "/storefronts";
        });
    }

    if (!form) return;

    const submitBtn = form.querySelector('button[type="submit"]');
    const submitLabel = submitBtn ? submitBtn.textContent : "";

    // HG-119 (Mattie Edozie, I4): loading state while the return is sent.
    function setSubmitting(isSubmitting) {
        if (!submitBtn) return;
        submitBtn.disabled = isSubmitting;
        submitBtn.textContent = isSubmitting ? "Submitting..." : submitLabel;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        clearFeedback();
        setSubmitting(true);

        try {
            const formData = new FormData(form);

            // HG-119: no X-User-Id / X-User-Role headers. The server reads
            // the user from the session cookie, which the browser sends itself.
            const response = await fetch("/returns", {
                method: "POST",
                body: formData
            });

            if (response.status === 401) {
                window.location.href = "/auth/login";
                return;
            }

            const result = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(result.error || "Failed to submit return.");
            }

            form.reset();
            if (damagePreview) damagePreview.innerHTML = "";
            showFeedback("Return submitted successfully");
            loadMyReturns();
        } catch (error) {
            console.error("Error submitting return:", error);
            showFeedback(error.message || "Something went wrong while submitting your return.", "error");
        } finally {
            setSubmitting(false);
        }
    });
});
