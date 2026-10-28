/*
listing_browse.js

  Hampton Garage Campus Marketplace
  Created by Clarence Bostic - Iteration 3
*/

(function () {
  "use strict";

  const PAGE_SIZE = 24;
  const priceFormat = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

  // Small helper: create an element with an optional class and text.
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  // "just now", "5 min ago", "3 hr ago", "2 days ago", then a date.
  function timeAgo(isoString) {
    if (!isoString) return "";
    const posted = new Date(isoString);
    if (Number.isNaN(posted.getTime())) return "";

    const seconds = Math.max(0, Math.floor((Date.now() - posted.getTime()) / 1000));
    if (seconds < 60) return "Just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes} min ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} hr ago`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days} ${days === 1 ? "day" : "days"} ago`;
    return posted.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }

  /*
  Builds one listing card.
  listing: an object from /api/listings/recent or /api/listings/categories/<name>
  options.showPosted: show "Posted 2 hr ago" (Recent Listings page)
  options.showCategories: show the storefront's category tags
  The whole card links to the storefront that sells the item.
  */
  function createListingCard(listing, options = {}) {
    const card = el("a", "listing-card browse-card");
    card.href = `/storefronts/${encodeURIComponent(listing.storefront_id)}`;
    card.setAttribute("aria-label", `${listing.title || "Listing"} from ${listing.brand_name || "a storefront"}`);

    // Image (or an empty placeholder when the seller has not uploaded one)
    const media = el("div", "browse-card-media");
    if (listing.image_url) {
      const img = el("img", "browse-card-img");
      img.src = listing.image_url;
      img.alt = listing.title || "";
      img.loading = "lazy";
      img.addEventListener("error", () => {
        img.remove();
        media.classList.add("is-empty");
      });
      media.appendChild(img);
    } else {
      media.classList.add("is-empty");
    }

    if (listing.status === "SOLD_OUT") {
      media.appendChild(el("span", "browse-badge browse-badge--sold", "Sold out"));
    } else if (listing.fulfillment_type === "PREORDER" || listing.is_made_to_order) {
      media.appendChild(el("span", "browse-badge", listing.is_made_to_order ? "Made to order" : "Preorder"));
    }
    card.appendChild(media);

    // Text
    const body = el("div", "browse-card-body");

    const brandRow = el("div", "browse-card-brand");
    if (listing.storefront_logo_url) {
      const logo = el("img", "browse-card-logo");
      logo.src = listing.storefront_logo_url;
      logo.alt = "";
      logo.loading = "lazy";
      logo.addEventListener("error", () => logo.remove());
      brandRow.appendChild(logo);
    }
    brandRow.appendChild(el("span", "browse-card-brand-name", listing.brand_name || "Storefront"));
    body.appendChild(brandRow);

    body.appendChild(el("h3", "browse-card-title", listing.title || "Untitled listing"));

    const meta = el("div", "browse-card-meta");
    const price = Number(listing.price);
    meta.appendChild(el("span", "browse-card-price", Number.isFinite(price) ? priceFormat.format(price) : ""));
    if (options.showPosted) {
      const posted = timeAgo(listing.created_at);
      if (posted) meta.appendChild(el("span", "browse-card-posted", posted));
    }
    body.appendChild(meta);

    if (options.showCategories && Array.isArray(listing.categories) && listing.categories.length) {
      const tags = el("div", "browse-card-tags");
      listing.categories.forEach(name => tags.appendChild(el("span", "browse-tag", name)));
      body.appendChild(tags);
    }

    card.appendChild(body);
    return card;
  }

  // GET a URL and return parsed JSON, or throw with the server's error message.
  async function fetchJson(url) {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    let data = null;
    try {
      data = await response.json();
    } catch (_) {
      // non-JSON error page
    }
    if (!response.ok) {
      const error = new Error((data && data.error) || `Request failed (${response.status})`);
      error.status = response.status;
      throw error;
    }
    return data;
  }

  // Replace a container's contents with a single message line.
  function showMessage(container, text) {
    container.replaceChildren(el("p", "browse-message", text));
  }

  /*
  Creates a pager that loads listings in batches of PAGE_SIZE.
    buildUrl(offset, limit) -> URL string for that batch
    grid       -> element the cards go into
    loadMoreBtn-> the "Load more" button (hidden when nothing is left)
    summary    -> element for "Showing 24 of 57 listings"
    cardOptions-> passed to createListingCard
    emptyText  -> message when there are no listings at all
  Call pager.reset() to start over (e.g. a different category).
  */
  function createPager({ buildUrl, grid, loadMoreBtn, summary, cardOptions, emptyText }) {
    let offset = 0;
    let total = 0;
    let loading = false;
    let generation = 0; // ignores responses from a previous reset()

    function updateSummary(shown) {
      if (!summary) return;
      summary.textContent = total
        ? `Showing ${shown} of ${total} ${total === 1 ? "listing" : "listings"}`
        : "";
    }

    async function loadNext() {
      if (loading) return;
      loading = true;
      const myGeneration = generation;
      loadMoreBtn.disabled = true;
      loadMoreBtn.textContent = "Loading…";

      try {
        const data = await fetchJson(buildUrl(offset, PAGE_SIZE));
        if (myGeneration !== generation) return;

        const listings = Array.isArray(data.listings) ? data.listings : [];
        total = Number(data.total) || 0;

        if (offset === 0) grid.replaceChildren();
        listings.forEach(listing => grid.appendChild(createListingCard(listing, cardOptions)));
        offset += listings.length;

        if (offset === 0) showMessage(grid, emptyText);
        updateSummary(offset);
        loadMoreBtn.hidden = offset >= total || listings.length === 0;
      } catch (error) {
        if (myGeneration !== generation) return;
        console.error("Could not load listings:", error);
        if (offset === 0) {
          showMessage(grid, "Could not load listings. Please try again.");
          loadMoreBtn.hidden = true;
        } else {
          loadMoreBtn.hidden = false; // let them retry the next batch
        }
      } finally {
        if (myGeneration === generation) {
          loading = false;
          loadMoreBtn.disabled = false;
          loadMoreBtn.textContent = "Load more";
        }
      }
    }

    function reset() {
      generation += 1;
      offset = 0;
      total = 0;
      loading = false;
      loadMoreBtn.hidden = true;
      loadMoreBtn.disabled = false;
      loadMoreBtn.textContent = "Load more";
      if (summary) summary.textContent = "";
      grid.replaceChildren();
      grid.appendChild(el("p", "browse-message", "Loading listings…"));
    }

    loadMoreBtn.addEventListener("click", loadNext);
    return { loadNext, reset };
  }

  // Side menu open/close (same behavior as the storefront home page).
  function setupNav() {
    const menuBtn = document.querySelector(".menu-btn");
    const navPane = document.getElementById("navPane");
    const navOverlay = document.getElementById("navOverlay");
    if (!menuBtn || !navPane || !navOverlay) return;

    const close = () => {
      navPane.classList.remove("active");
      navOverlay.classList.remove("active");
    };
    menuBtn.addEventListener("click", () => {
      navPane.classList.toggle("active");
      navOverlay.classList.toggle("active");
    });
    navOverlay.addEventListener("click", close);
    document.addEventListener("keydown", event => {
      if (event.key === "Escape") close();
    });
  }

  window.ListingBrowse = { el, createListingCard, createPager, fetchJson, showMessage, setupNav, timeAgo };
})();
