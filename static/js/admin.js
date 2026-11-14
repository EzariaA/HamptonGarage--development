// File Created By David Jackson
// showLoading, showEmpty, showMessage and showConfirm come from ui.js (loaded in base.html)

// The last list loaded for each table, so the delete buttons can find the item's name
let loadedUsers = [];
let loadedListings = [];
let loadedStorefronts = [];


// HELPERS

// Finds the item with this id in a list (or null if it isn't there)
function findById(list, id) {
    for (let i = 0; i < list.length; i++) {
        if (list[i].id === id) return list[i];
    }
    return null;
}

// Makes text safe to put in the table, so HTML in a username or title can't run
function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// Loads a list from the server into a table.
// Shows loading bars first, "nothing found" if the list is empty, or an error if it fails.
// makeRow(item) returns the <tr> HTML for one item. Returns the list (or [] on error).
async function loadTable(tableId, url, name, makeRow) {
    const table = document.querySelector(`#${tableId} tbody`);
    showLoading(table, 3);

    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error("Request failed");
        const items = await response.json();

        if (items.length === 0) {
            showEmpty(table, `No ${name} found.`);
            return items;
        }

        let rows = "";
        items.forEach(item => { rows += makeRow(item); });
        table.innerHTML = rows;
        return items;
    } catch (error) {
        showMessage(table, `Could not load ${name}. Please try again.`, "error");
        return [];
    }
}

// Asks "Are you sure?" and, if Yes, deletes with DELETE <url>,
// shows a green or red message at the bottom of the page, then reloads the table.
function confirmDelete(question, url, doneText, reloadTable) {
    showConfirm(question, async function () {
        try {
            const response = await fetch(url, { method: "DELETE" });
            if (!response.ok) throw new Error("Request failed");
            showMessage("adminMessage", `${doneText} was deleted.`, "success");
        } catch (error) {
            showMessage("adminMessage", `Could not delete ${doneText}. Please try again.`, "error");
        }
        reloadTable();
    });
}


// USERS  (GET /admin/users, DELETE /admin/users/<id>)

async function loadUsers() {
    loadedUsers = await loadTable("usersTable", "/admin/users", "users", user => `
        <tr>
            <td>${user.id}</td>
            <td>${escapeHtml(user.username)}</td>
            <td>${escapeHtml(user.email)}</td>
            <td>${escapeHtml(user.role || "user")}</td>
            <td>${escapeHtml(user.created_at)}</td>
            <td><button class="delete" onclick="deleteUser(${user.id})">Delete</button></td>
        </tr>`);
}

function deleteUser(userId) {
    const user = findById(loadedUsers, userId);
    const name = user ? (user.username || user.email) : "this user";
    confirmDelete(
        `Delete user "${name}" (ID ${userId})? This also deletes their storefront, listings, wishlist and returns. This can't be undone.`,
        `/admin/users/${userId}`, `User "${name}"`, loadUsers
    );
}


// LISTINGS  (GET /admin/listings, DELETE /admin/listings/<id>)

async function loadListings() {
    loadedListings = await loadTable("listingsTable", "/admin/listings", "listings", listing => `
        <tr>
            <td>${listing.id}</td>
            <td>${escapeHtml(listing.storefront_id)}</td>
            <td>${escapeHtml(listing.title)}</td>
            <td>${escapeHtml(listing.price)}</td>
            <td>${escapeHtml(listing.quantity_on_hand)}</td>
            <td>${escapeHtml(listing.status || "ACTIVE")}</td>
            <td>${escapeHtml(listing.fulfillment_type)}</td>
            <td>${escapeHtml(listing.created_at)}</td>
            <td><button class="delete" onclick="deleteListing(${listing.id})">Delete</button></td>
        </tr>`);
}

// Listings are "soft" deleted: hidden from the marketplace, not erased
function deleteListing(listingId) {
    const listing = findById(loadedListings, listingId);
    const name = listing ? listing.title : "this listing";
    confirmDelete(
        `Delete listing "${name}" (ID ${listingId})? It will be removed from the marketplace.`,
        `/admin/listings/${listingId}`, `Listing "${name}"`, loadListings
    );
}


// STOREFRONTS  (GET /admin/storefronts, DELETE /admin/storefronts/<id>)

async function loadStorefronts() {
    loadedStorefronts = await loadTable("storefrontsTable", "/admin/storefronts", "storefronts", store => `
        <tr>
            <td>${store.id}</td>
            <td>${escapeHtml(store.brand_name || store.name)}</td>
            <td>${escapeHtml(store.owner_id)}</td>
            <td><button class="delete" onclick="deleteStorefront(${store.id})">Delete</button></td>
        </tr>`);
}

function deleteStorefront(storeId) {
    const store = findById(loadedStorefronts, storeId);
    const name = store ? (store.brand_name || store.name || "this storefront") : "this storefront";
    confirmDelete(
        `Delete storefront "${name}" (ID ${storeId})? This also deletes all of its listings. This can't be undone.`,
        `/admin/storefronts/${storeId}`, `Storefront "${name}"`, loadStorefronts
    );
}


// RETURNS  (GET /admin/returns, PATCH /admin/returns/<id>)

async function loadReturns() {
    await loadTable("returnsTable", "/admin/returns", "return requests", item => `
        <tr>
            <td>${item.id}</td>
            <td>${escapeHtml(item.username)}<br><small>${escapeHtml(item.email)}</small></td>
            <td>${escapeHtml(item.order_number)}</td>
            <td>${item.has_damage ? "Yes" : "No"}</td>
            <td>${item.damage_image_url ? `<a href="${escapeHtml(item.damage_image_url)}" target="_blank">View</a>` : "—"}</td>
            <td>
                <select data-return-id="${item.id}">
                    <option value="pending" ${item.status === "pending" ? "selected" : ""}>Pending</option>
                    <option value="reviewed" ${item.status === "reviewed" ? "selected" : ""}>Reviewed</option>
                    <option value="resolved" ${item.status === "resolved" ? "selected" : ""}>Resolved</option>
                </select>
                <button onclick="saveReturnStatus(${item.id})">Save</button>
            </td>
            <td>${escapeHtml(item.reason)}</td>
        </tr>`);
}

// Saves the status picked in the dropdown for one return
async function saveReturnStatus(returnId) {
    const select = document.querySelector(`select[data-return-id="${returnId}"]`);
    if (!select) return;

    try {
        const response = await fetch(`/admin/returns/${returnId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: select.value })
        });
        if (!response.ok) throw new Error("Request failed");
        showMessage("adminMessage", `Return #${returnId} saved as "${select.value}".`, "success");
        loadReturns();
    } catch (error) {
        showMessage("adminMessage", "Failed to update return status. Please try again.", "error");
    }
}
