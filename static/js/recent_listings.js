/*
recent_listings.js
 Hampton Garage Campus Marketplace

  Created by Clarence Bostic - Iteration 3 
*/

(function () {
  "use strict";

  const { createPager, setupNav } = window.ListingBrowse;

  setupNav();

  const pager = createPager({
    buildUrl: (offset, limit) => `/api/listings/recent?limit=${limit}&offset=${offset}`,
    grid: document.getElementById("listingGrid"),
    loadMoreBtn: document.getElementById("loadMoreBtn"),
    summary: document.getElementById("browseSummary"),
    cardOptions: { showPosted: true, showCategories: true },
    emptyText: "No listings have been posted yet. Check back soon.",
  });

  pager.reset();
  pager.loadNext();
})();
