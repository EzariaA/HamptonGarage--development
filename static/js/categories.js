/*
categories.js
  Hampton Garage Campus Marketplace
  Created by Clarence Bostic - Iteration 3
*/

(function () {
  "use strict";

  const { el, createPager, fetchJson, setupNav } = window.ListingBrowse;

  setupNav();

  const searchForm = document.getElementById("categorySearchForm");
  const searchInput = document.getElementById("categorySearch");
  const categoryView = document.getElementById("categoryView");
  const categoryGrid = document.getElementById("categoryGrid");
  const categoryEmpty = document.getElementById("categoryEmpty");
  const listingsView = document.getElementById("categoryListingsView");
  const categoryTitle = document.getElementById("categoryTitle");
  const backBtn = document.getElementById("backToCategories");

  let categories = [];      // [{ name, listing_count }]
  let currentCategory = null;

  const pager = createPager({
    buildUrl: (offset, limit) =>
      `/api/listings/categories/${encodeURIComponent(currentCategory)}?limit=${limit}&offset=${offset}`,
    grid: document.getElementById("listingGrid"),
    loadMoreBtn: document.getElementById("loadMoreBtn"),
    summary: document.getElementById("browseSummary"),
    cardOptions: { showPosted: false, showCategories: false },
    emptyText: "No listings in this category yet.",
  });

  // ---------- All categories view ----------

  function createCategoryTile(category) {
    const tile = el("button", "category-tile");
    tile.type = "button";
    tile.dataset.name = category.name;

    tile.appendChild(el("span", "category-tile-name", category.name));
    const count = Number(category.listing_count) || 0;
    tile.appendChild(el("span", "category-tile-count", `${count} ${count === 1 ? "listing" : "listings"}`));
    if (count === 0) tile.classList.add("is-empty");

    tile.addEventListener("click", () => openCategory(category.name));
    return tile;
  }

  function renderCategories() {
    categoryGrid.replaceChildren(...categories.map(createCategoryTile));
    filterTiles();
  }

  // Hide tiles whose name doesn't contain the search text.
  function filterTiles() {
    const query = searchInput.value.trim().toLowerCase();
    let visible = 0;

    categoryGrid.querySelectorAll(".category-tile").forEach(tile => {
      const match = !query || tile.dataset.name.toLowerCase().includes(query);
      tile.hidden = !match;
      if (match) visible += 1;
    });

    if (categories.length && visible === 0) {
      categoryEmpty.textContent = `No category matches "${searchInput.value.trim()}". Try one of: ${categories.map(c => c.name).join(", ")}.`;
      categoryEmpty.hidden = false;
    } else {
      categoryEmpty.hidden = true;
    }
  }

  async function loadCategories() {
    categoryGrid.replaceChildren(el("p", "browse-message", "Loading categories…"));
    try {
      const data = await fetchJson("/api/listings/categories");
      categories = Array.isArray(data) ? data : [];
      renderCategories();
    } catch (error) {
      console.error("Could not load categories:", error);
      categoryGrid.replaceChildren(el("p", "browse-message", "Could not load categories. Please try again."));
    }
  }

  // ---------- Switching views ----------

  function findCategory(name) {
    if (!name) return null;
    const wanted = name.trim().toLowerCase();
    return categories.find(c => c.name.toLowerCase() === wanted) || null;
  }

  function showAllCategories() {
    currentCategory = null;
    listingsView.hidden = true;
    categoryView.hidden = false;
    document.title = "Categories | Hampton Garage";
    filterTiles();
  }

  function showCategory(name) {
    currentCategory = name;
    categoryTitle.textContent = name;
    categoryView.hidden = true;
    listingsView.hidden = false;
    document.title = `${name} | Hampton Garage`;
    pager.reset();
    pager.loadNext();
  }

  // Open a category and add it to browser history.
  function openCategory(name) {
    const category = findCategory(name);
    if (!category) return;
    const url = new URL(window.location.href);
    url.searchParams.set("category", category.name);
    history.pushState({ category: category.name }, "", url);
    showCategory(category.name);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function goBackToAll() {
    if (history.state && history.state.category) {
      history.back(); // popstate will show all categories
    } else {
      history.pushState({}, "", window.location.pathname);
      showAllCategories();
    }
  }

  // Render whatever the URL says (first load, refresh, Back/Forward).
  function syncFromUrl() {
    const requested = new URLSearchParams(window.location.search).get("category");
    const category = findCategory(requested);

    if (category) {
      showCategory(category.name);
    } else {
      if (requested) {
        categoryEmpty.textContent = `"${requested}" isn't a category. Pick one below.`;
        categoryEmpty.hidden = false;
        history.replaceState({}, "", window.location.pathname);
      }
      showAllCategories();
      if (requested) categoryEmpty.hidden = false;
    }
  }

  // ---------- Events ----------

  searchInput.addEventListener("input", () => {
    if (currentCategory) {
      // typing returns to the tile view
      history.pushState({}, "", window.location.pathname);
      showAllCategories();
    }
    filterTiles();
  });

  // Enter opens the first visible matching category.
  searchForm.addEventListener("submit", event => {
    event.preventDefault();
    const firstMatch = categoryGrid.querySelector(".category-tile:not([hidden])");
    if (firstMatch && searchInput.value.trim()) {
      searchInput.value = "";
      openCategory(firstMatch.dataset.name);
    }
  });

  backBtn.addEventListener("click", goBackToAll);
  window.addEventListener("popstate", syncFromUrl);

  // ---------- Start ----------
  loadCategories().then(syncFromUrl);
})();
