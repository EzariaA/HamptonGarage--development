// Clarence Bostic - Iteration 4

document.addEventListener("DOMContentLoaded", () => {
    const buttons = document.querySelectorAll(".map-spot-btn");
    const pin = document.getElementById("mapPin");
    const clearBtn = document.getElementById("mapClear");
    const locationBox = document.getElementById("meetingLocation");

    if (!buttons.length || !pin || !locationBox) return;

    const TAG = "(picked from campus map)";

    // Remove any line we added earlier so we don't stack up old picks for locations
    function removeOldPick() {
        return locationBox.value
            .split("\n")
            .filter(line => !line.includes(TAG))
            .join("\n")
            .trim();
    }

    buttons.forEach(btn => {
        btn.addEventListener("click", () => {
            // Move the pin
            pin.style.left = btn.dataset.x + "%";
            pin.style.top = btn.dataset.y + "%";
            pin.hidden = false;

            // Highlight only this button
            buttons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");

            // Spot goes on the first line, anything the buyer typed stays below it
            const note = removeOldPick();
            const pickLine = btn.dataset.name + " " + TAG;
            locationBox.value = note ? pickLine + "\n" + note : pickLine;

            if (clearBtn) clearBtn.hidden = false;
        });
    });

    if (clearBtn) {
        clearBtn.addEventListener("click", () => {
            pin.hidden = true;
            buttons.forEach(b => b.classList.remove("active"));
            locationBox.value = removeOldPick();
            clearBtn.hidden = true;
        });
    }
});