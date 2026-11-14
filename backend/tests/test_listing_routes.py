# Hampton Garage
# Listing route tests (services and S3 are mocked; no real listings are saved).
# Updated by Ava Bell - Iteration 4 (HG-115): tests now log in through the Flask session
# (session_transaction, same pattern as test_checkout.py) instead of the old X-User-Id header,
# which the server no longer reads. Added tests for the update and delete listing routes.

import io
import json
import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

CTRL = "controllers.listing_controller"
S3_UPLOAD = "utils.s3.upload_image_to_s3"

USER_ID = 42
STOREFRONT = {"id": 5, "name": "Ezaria's Closet"}
CREATED_LISTING = {"id": 101, "title": "Hampton Hoodie", "price": 25.0}


def image(name="hoodie.png"):
    """A fake uploaded image file."""
    return (io.BytesIO(b"fake image bytes"), name)


def listing_form(**overrides):
    """A valid Create Listing form; pass keyword arguments to change fields."""
    form = {
        "title": "Hampton Hoodie",
        "price": "25.00",
        "fulfillment_type": "IN_STOCK",
        "status": "ACTIVE",
        "sizes_available": json.dumps(["S", "M"]),
        "size_quantities": json.dumps({"S": 2, "M": 3}),
        "listing_images": [image()],
    }
    form.update(overrides)
    return form


class TestListingRoutes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with patch("app.create_vault_tables"):
            from app import create_app
            cls.app = create_app()
        cls.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app.test_client()

    def _login(self, user_id=USER_ID, role="user"):
        """Log the test client in the same way the real login does: through the session."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["role"] = role

    def post_form(self, form, logged_in=True):
        if logged_in:
            self._login()
        return self.client.post("/api/listings/create", data=form,
                                content_type="multipart/form-data")

    # ---------- Create listing: POST /api/listings/create ----------

    def test_create_listing_requires_login(self):
        res = self.post_form(listing_form(), logged_in=False)
        self.assertEqual(res.status_code, 401)

    @patch(f"{CTRL}.get_my_storefront_service", return_value=None)
    def test_create_listing_requires_storefront(self, _storefront):
        res = self.post_form(listing_form())
        self.assertEqual(res.status_code, 400)
        self.assertIn("storefront", res.get_json()["error"])

    @patch(f"{CTRL}.create_listing_service")
    @patch(f"{CTRL}.get_my_storefront_service", return_value=STOREFRONT)
    def test_create_listing_requires_title(self, _storefront, create):
        res = self.post_form(listing_form(title="   "))
        self.assertEqual(res.status_code, 400)
        create.assert_not_called()

    @patch(f"{CTRL}.create_listing_service")
    @patch(f"{CTRL}.get_my_storefront_service", return_value=STOREFRONT)
    def test_create_listing_requires_a_size(self, _storefront, create):
        res = self.post_form(listing_form(sizes_available="[]"))
        self.assertEqual(res.status_code, 400)
        create.assert_not_called()

    @patch(f"{CTRL}.create_listing_service")
    @patch(f"{CTRL}.get_my_storefront_service", return_value=STOREFRONT)
    def test_create_listing_requires_an_image(self, _storefront, create):
        form = listing_form()
        del form["listing_images"]
        res = self.post_form(form)
        self.assertEqual(res.status_code, 400)
        create.assert_not_called()

    @patch(f"{CTRL}.create_listing_service")
    @patch(f"{CTRL}.get_my_storefront_service", return_value=STOREFRONT)
    def test_create_listing_rejects_more_than_four_images(self, _storefront, create):
        res = self.post_form(listing_form(listing_images=[image(f"p{i}.png") for i in range(5)]))
        self.assertEqual(res.status_code, 400)
        create.assert_not_called()

    @patch(S3_UPLOAD)
    @patch(f"{CTRL}.create_listing_service")
    @patch(f"{CTRL}.get_my_storefront_service", return_value=STOREFRONT)
    def test_create_listing_rejects_non_image_file(self, _storefront, create, upload):
        res = self.post_form(listing_form(listing_images=[image("notes.pdf")]))
        self.assertEqual(res.status_code, 400)
        upload.assert_not_called()
        create.assert_not_called()

    @patch(S3_UPLOAD, return_value=None)
    @patch(f"{CTRL}.create_listing_service")
    @patch(f"{CTRL}.get_my_storefront_service", return_value=STOREFRONT)
    def test_create_listing_fails_cleanly_when_s3_upload_fails(self, _storefront, create, _upload):
        res = self.post_form(listing_form())
        self.assertEqual(res.status_code, 500)
        create.assert_not_called()  # no listing is saved without its image

    @patch(f"{CTRL}.upsert_listing_size_service")
    @patch(f"{CTRL}.add_listing_image_service")
    @patch(f"{CTRL}.create_listing_service", return_value=CREATED_LISTING)
    @patch(S3_UPLOAD, side_effect=["https://s3.test/listings/1.png", "https://s3.test/listings/2.png"])
    @patch(f"{CTRL}.get_my_storefront_service", return_value=STOREFRONT)
    def test_create_listing_success(self, _storefront, upload, create, add_image, upsert_size):
        res = self.post_form(listing_form(listing_images=[image("front.png"), image("back.jpg")]))

        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.get_json()["id"], 101)

        # Listing saved in the user's own storefront, quantity = sum of size quantities
        user, storefront_id, data = create.call_args.args
        self.assertEqual(user["id"], USER_ID)
        self.assertEqual(storefront_id, STOREFRONT["id"])
        self.assertEqual(data["title"], "Hampton Hoodie")
        self.assertEqual(data["price"], 25.0)
        self.assertEqual(data["quantity_on_hand"], 5)

        # Both images uploaded to the "listings" folder; only the first is primary
        self.assertEqual(upload.call_count, 2)
        self.assertEqual(upload.call_args.kwargs["folder"], "listings")
        primaries = [c.kwargs["is_primary"] for c in add_image.call_args_list]
        self.assertEqual(primaries, [True, False])

        # One size row per size, with its own quantity
        sizes = {c.args[2]: c.args[3] for c in upsert_size.call_args_list}
        self.assertEqual(sizes, {"S": 2, "M": 3})

    # ---------- View listing: GET /api/listings/<id> ----------

    @patch(f"{CTRL}.get_listing_by_id_service", return_value=CREATED_LISTING)
    def test_get_listing_success(self, _get):
        res = self.client.get("/api/listings/101")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["title"], "Hampton Hoodie")

    @patch(f"{CTRL}.get_listing_by_id_service", side_effect=Exception("Listing not found"))
    def test_get_listing_not_found(self, _get):
        res = self.client.get("/api/listings/999")
        self.assertEqual(res.status_code, 404)

    # ---------- Update listing: PUT /api/listings/<id> (added HG-115) ----------

    @patch(f"{CTRL}.update_listing_service")
    def test_update_listing_requires_login(self, update):
        res = self.client.put("/api/listings/101", json={"title": "New Title"})
        self.assertEqual(res.status_code, 401)
        update.assert_not_called()

    @patch(f"{CTRL}.update_listing_service", return_value=dict(CREATED_LISTING, title="New Title", price=30.0))
    def test_update_listing_success(self, update):
        self._login()
        res = self.client.put("/api/listings/101", json={"title": "New Title", "price": 30})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["title"], "New Title")
        user, listing_id, data = update.call_args.args
        self.assertEqual((user["id"], listing_id), (USER_ID, 101))
        self.assertEqual(data, {"title": "New Title", "price": 30})

    @patch(f"{CTRL}.update_listing_service", side_effect=Exception("Unauthorized action."))
    def test_update_someone_elses_listing_is_forbidden(self, _update):
        self._login()
        res = self.client.put("/api/listings/101", json={"title": "Not Mine"})
        self.assertEqual(res.status_code, 403)

    @patch(f"{CTRL}.update_listing_service", side_effect=Exception("Listing not found."))
    def test_update_missing_listing_returns_404(self, _update):
        self._login()
        res = self.client.put("/api/listings/999", json={"title": "Ghost"})
        self.assertEqual(res.status_code, 404)

    @patch(f"{CTRL}.update_listing_service", side_effect=Exception("price cannot be negative."))
    def test_update_with_invalid_data_returns_400(self, _update):
        self._login()
        res = self.client.put("/api/listings/101", json={"price": -5})
        self.assertEqual(res.status_code, 400)
        self.assertIn("price", res.get_json()["error"])

    # ---------- Delete listing: DELETE /api/listings/<id> (added HG-115) ----------

    @patch(f"{CTRL}.delete_listing_service")
    def test_delete_listing_requires_login(self, delete):
        res = self.client.delete("/api/listings/101")
        self.assertEqual(res.status_code, 401)
        delete.assert_not_called()

    @patch(f"{CTRL}.delete_listing_service", return_value=dict(CREATED_LISTING, status="DELETED"))
    def test_delete_listing_success(self, delete):
        self._login()
        res = self.client.delete("/api/listings/101")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["status"], "DELETED")
        user, listing_id = delete.call_args.args
        self.assertEqual((user["id"], listing_id), (USER_ID, 101))

    @patch(f"{CTRL}.delete_listing_service", side_effect=Exception("Unauthorized action."))
    def test_delete_someone_elses_listing_is_forbidden(self, _delete):
        self._login()
        res = self.client.delete("/api/listings/101")
        self.assertEqual(res.status_code, 403)

    @patch(f"{CTRL}.delete_listing_service", side_effect=Exception("Listing not found."))
    def test_delete_missing_listing_returns_404(self, _delete):
        self._login()
        res = self.client.delete("/api/listings/999")
        self.assertEqual(res.status_code, 404)

    # ---------- Listing images ----------

    @patch(f"{CTRL}.add_listing_image_service", return_value={"id": 7, "image_url": "https://s3.test/x.png"})
    def test_add_image_success(self, add_image):
        self._login()
        res = self.client.post("/api/listings/101/images",
                               json={"image_url": "https://s3.test/x.png", "is_primary": True})
        self.assertEqual(res.status_code, 201)
        user, listing_id, url, is_primary = add_image.call_args.args
        self.assertEqual((user["id"], listing_id, url, is_primary), (USER_ID, 101, "https://s3.test/x.png", True))

    @patch(f"{CTRL}.add_listing_image_service", side_effect=Exception("Unauthorized: not your listing"))
    def test_add_image_to_someone_elses_listing_is_forbidden(self, _add):
        self._login()
        res = self.client.post("/api/listings/101/images",
                               json={"image_url": "https://s3.test/x.png"})
        self.assertEqual(res.status_code, 403)

    @patch(f"{CTRL}.get_listing_images_service",
           return_value=[{"id": 7, "is_primary": True}, {"id": 8, "is_primary": False}])
    def test_get_images_success(self, _get):
        res = self.client.get("/api/listings/101/images")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.get_json()), 2)

    @patch(f"{CTRL}.get_listing_images_service", side_effect=Exception("Listing not found"))
    def test_get_images_listing_not_found(self, _get):
        res = self.client.get("/api/listings/999/images")
        self.assertEqual(res.status_code, 404)

    @patch(f"{CTRL}.set_primary_image_service", return_value={"id": 8, "is_primary": True})
    def test_set_primary_image_success(self, set_primary):
        self._login()
        res = self.client.patch("/api/listings/101/images/8/primary")
        self.assertEqual(res.status_code, 200)
        user, listing_id, image_id = set_primary.call_args.args
        self.assertEqual((user["id"], listing_id, image_id), (USER_ID, 101, 8))

    @patch(f"{CTRL}.delete_listing_image_service", side_effect=Exception("Image not found"))
    def test_delete_missing_image_returns_404(self, _delete):
        self._login()
        res = self.client.delete("/api/listings/101/images/999")
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()