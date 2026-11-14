# Tests for the campus map side buttons on the checkout page
# Created by Clarence Bostic - Iteration 4
# This was created by Claude, for my Iteration4 Tests! YAY TESTS!

import os
import re
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

os.environ.setdefault("SECRET_KEY", "test-secret")

from app import create_app

COMMON_SPOTS = [
    "Student Center",
    "Harvey Library",
    "Convocation Center",
    "Memorial Church",
    "Emancipation Oak",
    "Holly Tree Inn",
]

JS_PATH = os.path.join(PROJECT_ROOT, "static", "js", "campus_map_picker.js")
MAP_PATH = os.path.join(PROJECT_ROOT, "static", "images", "campus_map.jpg")


class TestCampusMapButtons(unittest.TestCase):

    def setUp(self):
        # Don't touch the real database when the app starts
        with patch("init_db.create_vault_tables"):
            app = create_app()
        app.config["TESTING"] = True
        self.client = app.test_client()

        # Checkout needs a logged in user
        with self.client.session_transaction() as sess:
            sess["user"] = {"id": 1, "username": "tester"}

        self.html = self.client.get("/checkout").get_data(as_text=True)

    # ---------- The page ----------

    def test_checkout_page_loads_when_logged_in(self):
        self.assertEqual(self.client.get("/checkout").status_code, 200)

    def test_checkout_redirects_when_logged_out(self):
        with self.client.session_transaction() as sess:
            sess.clear()
        self.assertEqual(self.client.get("/checkout").status_code, 302)

    def test_page_has_map_image_pin_and_sidebar(self):
        for element_id in ("mapSpots", "campusMap", "mapPin", "mapClear", "meetingLocation"):
            self.assertIn(f'id="{element_id}"', self.html)

    def test_page_loads_the_picker_script(self):
        self.assertIn("js/campus_map_picker.js", self.html)

    # ---------- The buttons ----------

    def test_there_is_one_button_per_common_spot(self):
        buttons = re.findall(r'class="map-spot-btn"', self.html)
        self.assertEqual(len(buttons), len(COMMON_SPOTS))

    def test_every_common_spot_has_a_button(self):
        for name in COMMON_SPOTS:
            self.assertIn(f'data-name="{name}"', self.html)

    def test_button_positions_are_on_the_map(self):
        # x and y are percents, so they must be between 0 and 100
        spots = re.findall(r'data-x="([\d.]+)" data-y="([\d.]+)"', self.html)
        self.assertEqual(len(spots), len(COMMON_SPOTS))
        for x, y in spots:
            self.assertTrue(0 <= float(x) <= 100)
            self.assertTrue(0 <= float(y) <= 100)

    def test_buttons_do_not_submit_the_form(self):
        # A plain <button> inside a form submits it, so each one needs type="button"
        buttons = re.findall(r'<button[^>]*class="map-(?:spot|clear)-btn"[^>]*>', self.html)
        for tag in buttons:
            self.assertIn('type="button"', tag)

    # ---------- The script ----------

    def test_script_is_served(self):
        response = self.client.get("/static/js/campus_map_picker.js")
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_map_picture_has_no_click_handler(self):
        # The map is only a picture now; picking happens with the buttons
        with open(JS_PATH) as f:
            js = f.read()
        self.assertNotIn("campusMap", js)
        self.assertIn(".map-spot-btn", js)

    # ---------- The map picture ----------

    @unittest.skipUnless(os.path.exists(MAP_PATH), "campus_map.jpg not in static/images")
    def test_map_image_is_served(self):
        response = self.client.get("/static/images/campus_map.jpg")
        self.assertEqual(response.status_code, 200)
        response.close()


if __name__ == "__main__":
    unittest.main()