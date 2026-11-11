/*
    campus_map_picker.js
    The Vault Campus Marketplace
    Added by Clarence Bostic - 11/10/26

    Lets the buyer pick a meet-up spot on the Hampton campus map at checkout.
    - Tap anywhere on the map to drop a pin; the closest landmark fills in the Meeting Location box
    - Or tap one of the common spots under the map
    - Anything the buyer typed (like "1st floor") stays under the map pick
    No backend change: the result is still a normal meeting_location string.
*/

// Landmarks on static/images/campus_map.jpg, as % of the image width (x) and height (y)
const CAMPUS_SPOTS = [
    { name: "Student Center", x: 52.0, y: 46.7, common: true },
    { name: "Harvey Library", x: 42.8, y: 29.4, common: true },
    { name: "Convocation Center", x: 81.4, y: 22.9, common: true },
    { name: "Memorial Church", x: 68.4, y: 79.7, common: true },
    { name: "Emancipation Oak", x: 47.2, y: 7.3, common: true },
    { name: "Holly Tree Inn", x: 48.3, y: 72.6, common: true },
    { name: "Armstrong Stadium", x: 68.4, y: 36.4 },
    { name: "Ogden Hall", x: 61.1, y: 83.4 },
    { name: "Olin Engineering Building", x: 57.7, y: 14.3 },
    { name: "Science & Technology Building", x: 58.3, y: 54.8 },
    { name: "New Dining Facility", x: 31.0, y: 66.1 },
    { name: "Marine Point / Sailboat Dock", x: 89.0, y: 86.4 },
    { name: "Jerome Holland Hall", x: 56.7, y: 19.6 },
    { name: "Booker T. Washington Memorial", x: 46.0, y: 23.2 },
    { name: "Computer Center", x: 66.7, y: 67.6 },
    { name: "Health Services & Campus Safety", x: 33.0, y: 36.5 },
];

document.addEventListener("DOMContentLoaded", () => {
    const map = document.getElementById("campusMap");
    const pin = document.getElementById("mapPin");
    const spotsBox = document.getElementById("mapSpots");
    const selection = document.getElementById("mapSelection");
    const clearBtn = document.getElementById("mapClear");
    const meetingBox = document.getElementById("meetingLocation");
    if (!map || !pin || !meetingBox) return;

    let lastMapText = "";

    // closest landmark to a point; the image is taller than wide, so compare in pixels
    function closestSpot(x, y) {
        const w = map.clientWidth, h = map.clientHeight;
        let best = CAMPUS_SPOTS[0], bestDist = Infinity;
        for (const spot of CAMPUS_SPOTS) {
            const dx = (spot.x - x) / 100 * w;
            const dy = (spot.y - y) / 100 * h;
            const dist = dx * dx + dy * dy;
            if (dist < bestDist) { best = spot; bestDist = dist; }
        }
        return best;
    }

    function pickSpot(x, y, spotName) {
        pin.style.left = `${x}%`;
        pin.style.top = `${y}%`;
        pin.hidden = false;

        const mapText = `Near ${spotName} (picked on campus map)`;

        // keep anything the buyer typed, and put the map pick on the first line
        let note = meetingBox.value;
        if (lastMapText && note.startsWith(lastMapText)) note = note.slice(lastMapText.length);
        note = note.trim();
        meetingBox.value = note ? `${mapText}\n${note}` : mapText;
        lastMapText = mapText;

        if (selection) selection.textContent = `Meet-up spot: ${spotName}`;
        if (clearBtn) clearBtn.hidden = false;
        spotsBox?.querySelectorAll("button").forEach(b => {
            b.classList.toggle("active", b.dataset.name === spotName);
        });
    }

    // tap or click on the map
    map.addEventListener("click", (e) => {
        const box = map.getBoundingClientRect();
        const x = (e.clientX - box.left) / box.width * 100;
        const y = (e.clientY - box.top) / box.height * 100;
        pickSpot(x, y, closestSpot(x, y).name);
    });

    // quick-pick buttons for the common spots
    if (spotsBox) {
        for (const spot of CAMPUS_SPOTS.filter(s => s.common)) {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "map-spot-btn";
            btn.dataset.name = spot.name;
            btn.textContent = spot.name;
            btn.addEventListener("click", () => pickSpot(spot.x, spot.y, spot.name));
            spotsBox.appendChild(btn);
        }
    }

    // clear the map pick but keep the buyer's own note
    clearBtn?.addEventListener("click", () => {
        if (lastMapText && meetingBox.value.startsWith(lastMapText)) {
            meetingBox.value = meetingBox.value.slice(lastMapText.length).trim();
        }
        lastMapText = "";
        pin.hidden = true;
        clearBtn.hidden = true;
        if (selection) selection.textContent = "";
        spotsBox?.querySelectorAll("button").forEach(b => b.classList.remove("active"));
    });
});