# Hampton Garage
# Tests for the campus map picker on the checkout page
# Added by Clarence Bostic 
#
# Run them:   python -m unittest backend.tests.test_campus_map_picker -v
# No database, no Stripe, and no internet needed.

import os
import re
import struct
import sys
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

os.environ.setdefault("SECRET_KEY", "test-secret-key")

JS_PATH = os.path.join(PROJECT_ROOT, "static", "js", "campus_map_picker.js")
CSS_PATH = os.path.join(PROJECT_ROOT, "static", "css", "checkout.css")
IMG_PATH = os.path.join(PROJECT_ROOT, "static", "images", "campus_map.jpg")
TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "templates", "checkout.html")

# The landmark positions were measured on this exact image size.
EXPECTED_IMG_SIZE = (880, 1070)
COMMON_SPOTS = [
    "Student Center", "Harvey Library", "Convocation Center",
    "Memorial Church", "Emancipation Oak", "Holly Tree Inn",
]
CART = [{"id": 7, "name": "Hampton Hoodie", "price": 25.00, "quantity": 1, "size": "M"}]
USER_ID = 42


def load_spots():
    """Read the CAMPUS_SPOTS list out of the JavaScript file."""
    with open(JS_PATH, encoding="utf-8") as f:
        js = f.read()
    block = re.search(r"const CAMPUS_SPOTS = \[(.*?)\];", js, re.S).group(1)
    spots = []
    for m in re.finditer(r'\{\s*name:\s*"([^"]+)",\s*x:\s*([\d.]+),\s*y:\s*([\d.]+)(,\s*common:\s*true)?\s*\}', block):
        spots.append({"name": m.group(1), "x": float(m.group(2)), "y": float(m.group(3)),
                      "common": bool(m.group(4))})
    return spots


def jpeg_size(path):
    """Width and height of a JPEG, read from its header (no extra libraries needed)."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG")
    i = 2
    while i < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        length = struct.unpack(">H", data[i + 2:i + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2):  # start-of-frame holds the size
            height, width = struct.unpack(">HH", data[i + 5:i + 9])
            return width, height
        i += 2 + length
    raise ValueError("no size found in JPEG")


def make_app():
    # create_app() normally builds the database tables; skip that, these tests need no database
    with patch("init_db.create_vault_tables"):
        from app import create_app
        app = create_app()
    app.config["TESTING"] = True
    return app


# ________________________________________________________
# PART 1: the checkout page shows the map picker
# ________________________________________________________

class TestMapPickerPage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = make_app()

    def setUp(self):
        self.client = self.app.test_client()

    def _page(self):
        with self.client.session_transaction() as sess:
            sess["user"] = "tester"
            sess["user_id"] = USER_ID
            sess["cart"] = CART
        res = self.client.get("/checkout")
        self.assertEqual(res.status_code, 200)
        return res.get_data(as_text=True)

    def test_checkout_page_still_requires_login(self):
        res = self.client.get("/checkout")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers["Location"])

    def test_map_container_and_image_are_on_the_page(self):
        html = self._page()
        self.assertIn('id="campusMap"', html)
        self.assertIn('class="map-frame"', html)
        self.assertIn("/static/images/campus_map.jpg", html)
        self.assertIn('alt="Hampton University campus map"', html)

    def test_pin_and_clear_button_start_hidden(self):
        html = self._page()
        self.assertRegex(html, r'id="mapPin"[^>]*hidden')
        self.assertRegex(html, r'id="mapClear"[^>]*hidden')

    def test_quick_pick_area_and_selection_label_exist(self):
        html = self._page()
        self.assertIn('id="mapSpots"', html)
        self.assertIn('id="mapSelection"', html)

    def test_meeting_location_box_is_kept_and_still_required(self):
        # checkout.js reads this box when the buyer pays, so it must stay
        html = self._page()
        self.assertRegex(html, r'<textarea id="meetingLocation"[^>]*required')

    def test_clear_button_does_not_submit_the_form(self):
        html = self._page()
        self.assertRegex(html, r'<button type="button" id="mapClear"')

    def test_picker_script_loads_after_checkout_script(self):
        html = self._page()
        checkout_js = html.find("/static/js/checkout.js")
        picker_js = html.find("/static/js/campus_map_picker.js")
        self.assertNotEqual(checkout_js, -1)
        self.assertNotEqual(picker_js, -1)
        self.assertLess(checkout_js, picker_js)

    def test_map_sits_inside_the_checkout_form(self):
        html = self._page()
        form_start = html.find('id="checkoutForm"')
        form_end = html.find("</form>", form_start)
        self.assertTrue(form_start < html.find('id="campusMap"') < form_end)


# ________________________________________________________
# PART 2: the new static files are served
# ________________________________________________________

class TestMapPickerStaticFiles(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = make_app().test_client()

    def test_picker_javascript_is_served(self):
        res = self.client.get("/static/js/campus_map_picker.js")
        self.assertEqual(res.status_code, 200)
        self.assertIn("javascript", res.content_type)
        res.close()

    def test_map_image_is_served_as_jpeg(self):
        res = self.client.get("/static/images/campus_map.jpg")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, "image/jpeg")
        res.close()

    def test_checkout_css_has_every_map_style(self):
        with open(CSS_PATH, encoding="utf-8") as f:
            css = f.read()
        for selector in (".map-picker", ".map-spots", ".map-spot-btn", ".map-spot-btn.active",
                         ".map-frame", ".map-frame img", ".map-pin", ".map-pin[hidden]",
                         ".map-selection-row", ".map-selection", ".map-clear-btn"):
            self.assertIn(selector + " {", css, f"missing CSS rule for {selector}")

    def test_map_frame_is_positioned_so_the_pin_can_sit_on_it(self):
        with open(CSS_PATH, encoding="utf-8") as f:
            css = f.read()
        frame = re.search(r"\.map-frame \{(.*?)\}", css, re.S).group(1)
        pin = re.search(r"\.map-pin \{(.*?)\}", css, re.S).group(1)
        self.assertIn("position: relative", frame)
        self.assertIn("position: absolute", pin)
        self.assertIn("pointer-events: none", pin)  # clicks go through the pin to the map


# ________________________________________________________
# PART 3: the landmark list is valid
# ________________________________________________________

class TestLandmarkData(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.spots = load_spots()

    def test_all_landmarks_were_read(self):
        with open(JS_PATH, encoding="utf-8") as f:
            listed = re.search(r"const CAMPUS_SPOTS = \[(.*?)\];", f.read(), re.S).group(1).count("name:")
        self.assertEqual(len(self.spots), listed, "a landmark line is written in an unexpected format")
        self.assertGreaterEqual(len(self.spots), 10)

    def test_names_are_unique(self):
        names = [s["name"] for s in self.spots]
        self.assertEqual(len(names), len(set(names)))

    def test_every_landmark_is_on_the_map(self):
        for s in self.spots:
            with self.subTest(spot=s["name"]):
                self.assertTrue(0 < s["x"] < 100)
                self.assertTrue(0 < s["y"] < 100)

    def test_the_six_common_spots_get_buttons(self):
        common = [s["name"] for s in self.spots if s["common"]]
        self.assertEqual(common, COMMON_SPOTS)

    def test_no_two_landmarks_are_on_top_of_each_other(self):
        # if two were closer than ~2% of the map, a tap could never pick one of them
        w, h = EXPECTED_IMG_SIZE
        for i, a in enumerate(self.spots):
            for b in self.spots[i + 1:]:
                dx = (a["x"] - b["x"]) / 100 * w
                dy = (a["y"] - b["y"]) / 100 * h
                with self.subTest(a=a["name"], b=b["name"]):
                    self.assertGreater((dx * dx + dy * dy) ** 0.5, 20)

    def test_meeting_text_format(self):
        with open(JS_PATH, encoding="utf-8") as f:
            js = f.read()
        self.assertIn("`Near ${spotName} (picked on campus map)`", js)


# ________________________________________________________
# PART 4: the map image is the one the positions were measured on
# ________________________________________________________

class TestMapImage(unittest.TestCase):

    def test_image_exists(self):
        self.assertTrue(os.path.isfile(IMG_PATH), "static/images/campus_map.jpg is missing")

    def test_image_is_a_real_jpeg(self):
        with open(IMG_PATH, "rb") as f:
            self.assertEqual(f.read(2), b"\xff\xd8")

    def test_image_size_matches_the_landmark_positions(self):
        # a different crop or size would put every pin in the wrong place
        self.assertEqual(jpeg_size(IMG_PATH), EXPECTED_IMG_SIZE)

    def test_image_is_small_enough_for_phones(self):
        self.assertLess(os.path.getsize(IMG_PATH), 500 * 1024)


# ________________________________________________________
# PART 5: the server accepts a meeting location made by the map
# (Stripe and the database are mocked, like test_checkout.py)
# ________________________________________________________

CTRL = "controllers.checkout_controller"


class TestCheckoutAcceptsMapLocation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = make_app()

    def setUp(self):
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = USER_ID
            sess["cart"] = CART

    def _buyer(self, meeting):
        return {"first_name": "Test", "last_name": "Buyer", "email": "buyer@my.hamptonu.edu",
                "contact": "757-555-0100", "meeting_location": meeting}

    @patch(f"{CTRL}.check_listing_availability")
    @patch(f"{CTRL}.get_listing_by_id", return_value={"price": 25.00})
    @patch(f"{CTRL}.stripe")
    def test_map_pick_with_a_typed_note_is_saved_exactly(self, stripe_mock, _listing, _avail):
        stripe_mock.checkout.Session.create.return_value = MagicMock(url="https://stripe.test/pay")
        meeting = "Near Memorial Church (picked on campus map)\n1st floor by the bookstore"

        res = self.client.post("/api/checkout/create-session", json=self._buyer(meeting))

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["url"], "https://stripe.test/pay")
        with self.client.session_transaction() as sess:
            self.assertEqual(sess["pending_buyer"]["meeting_location"], meeting)

    @patch(f"{CTRL}.stripe")
    def test_empty_meeting_location_is_still_rejected(self, stripe_mock):
        res = self.client.post("/api/checkout/create-session", json=self._buyer("   "))
        self.assertEqual(res.status_code, 400)
        stripe_mock.checkout.Session.create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
