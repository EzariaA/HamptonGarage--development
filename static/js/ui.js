// "box" can be an element id like "formMessage" or the element itself.

// Turns an id into the real element (or returns the element as is)
function getBox(box) {
    if (typeof box === "string") return document.getElementById(box);
    return box;
}

// Clears the box and puts the item inside.
// A table <tbody> can only hold rows, so the item goes in one cell that spans every column.
function putInBox(box, item) {
    box.innerHTML = "";
    if (box.tagName !== "TBODY") {
        box.appendChild(item);
        return;
    }
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = box.closest("table").querySelectorAll("thead th").length || 1;
    cell.appendChild(item);
    row.appendChild(cell);
    box.appendChild(row);
}

// Shows a colored message instead of alert(). type: "success", "error" or "info"
// Example: showMessage("formMessage", "Storefront saved!", "success");
function showMessage(box, text, type) {
    box = getBox(box);
    if (!box) return;
    type = type || "info";

    const message = document.createElement("div");
    message.className = "ui-message ui-message-" + type;
    message.setAttribute("role", type === "error" ? "alert" : "status");

    // textContent keeps any HTML in the text from running
    const words = document.createElement("span");
    words.textContent = text;

    // Small x that closes the message
    const close = document.createElement("button");
    close.type = "button";
    close.className = "ui-message-close";
    close.setAttribute("aria-label", "Close message");
    close.textContent = "×";
    close.onclick = function () { message.remove(); };

    message.append(words, close);
    putInBox(box, message);
}

// Shows pulsing gray bars while data loads (rows = how many bars, default 3)
// Example: showLoading("listingsContainer", 4);
function showLoading(box, rows) {
    box = getBox(box);
    if (!box) return;

    const loading = document.createElement("div");
    loading.className = "ui-loading";
    loading.setAttribute("role", "status");
    loading.setAttribute("aria-label", "Loading");

    for (let i = 0; i < (rows || 3); i++) {
        const bar = document.createElement("div");
        bar.className = "ui-loading-bar";
        loading.appendChild(bar);
    }
    putInBox(box, loading);
}

// Shows gray "nothing here" text
// Example: showEmpty("listingsContainer", "You don't have any listings yet.");
function showEmpty(box, text) {
    box = getBox(box);
    if (!box) return;

    const empty = document.createElement("p");
    empty.className = "ui-empty";
    empty.textContent = text || "Nothing here yet.";
    putInBox(box, empty);
}

// Shows an "Are you sure?" popup instead of confirm(). onYes only runs if the user clicks Yes.
// Cancel, clicking outside the popup, or Escape closes it.
// Example: showConfirm("Delete storefront 'Onyx'?", function () { deleteStorefront(4); });
function showConfirm(text, onYes) {
    const overlay = document.createElement("div");
    overlay.className = "ui-confirm-overlay";
    overlay.innerHTML = `
        <div class="ui-confirm" role="dialog" aria-modal="true">
            <h3>Are you sure?</h3>
            <p></p>
            <div class="ui-confirm-buttons">
                <button type="button" class="ui-confirm-cancel">Cancel</button>
                <button type="button" class="ui-confirm-yes">Yes, delete</button>
            </div>
        </div>`;
    overlay.querySelector("p").textContent = text; // textContent so names can't add HTML
    document.body.appendChild(overlay);

    const cancelButton = overlay.querySelector(".ui-confirm-cancel");
    const yesButton = overlay.querySelector(".ui-confirm-yes");

    // Removes the popup and stops listening for Escape
    function closePopup() {
        overlay.remove();
        document.removeEventListener("keydown", escapeKey);
    }
    function escapeKey(event) {
        if (event.key === "Escape") closePopup();
    }

    document.addEventListener("keydown", escapeKey);
    cancelButton.onclick = closePopup;
    overlay.onclick = function (event) {
        if (event.target === overlay) closePopup(); // only the dark background, not the white box
    };
    yesButton.onclick = function () {
        closePopup();
        if (onYes) onYes();
    };

    cancelButton.focus(); // start on Cancel so Enter doesn't delete by accident
}
