# Iteration 4 unit tests - Makena Jelks
# Covers: storefront create, edit, delete, and image upload routes.
# The database and S3 are mocked. The real storefront_service still runs,
# so its validation and ownership rules are tested through the routes.

import os
import sys
import unittest
from io import BytesIO
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

SVC = "services.storefront_service"
S3_UPLOAD = "utils.s3.upload_image_to_s3"

OWNER_ID = 3
OTHER_ID = 9
STOREFRONT = {"id": 5, "owner_id": OWNER_ID, "brand_name": "Kicks", "is_active": True}
UPLOAD_URL = "/api/storefronts/upload-image"


class BaseTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with patch("app.create_vault_tables"):
            from app import create_app
            cls.app = create_app()
        cls.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app.test_client()

    def log_in_as(self, user_id, role="user"):
        with self.client.session_transaction() as sess:
            sess["user"] = f"user{user_id}"
            sess["user_id"] = user_id
            sess["role"] = role

    def flashes(self):
        with self.client.session_transaction() as sess:
            return sess.get("_flashes", [])


# ______________________________________________________________
# CREATE  -  POST /api/storefronts
# ______________________________________________________________
class TestCreateStorefront(BaseTest):

    @patch(f"{SVC}.create_storefront", return_value={"id": 5, "brand_name": "Kicks"})
    @patch(f"{SVC}.get_storefront_by_owner_id", return_value=None)
    def test_create_storefront_success(self, _existing, mock_create):
        self.log_in_as(OWNER_ID)
        res = self.client.post("/api/storefronts", json={"brand_name": "  Kicks  "})
        self.assertEqual(res.status_code, 201)
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs["owner_id"], OWNER_ID)
        self.assertEqual(kwargs["brand_name"], "Kicks")

    @patch(f"{SVC}.create_storefront")
    def test_create_storefront_requires_login(self, mock_create):
        res = self.client.post("/api/storefronts", json={"brand_name": "Kicks"})
        self.assertEqual(res.status_code, 401)
        mock_create.assert_not_called()

    @patch(f"{SVC}.create_storefront")
    def test_create_storefront_ignores_user_id_header(self, mock_create):
        res = self.client.post("/api/storefronts", json={"brand_name": "Kicks"},
                               headers={"X-User-Id": str(OWNER_ID)})
        self.assertEqual(res.status_code, 401)
        mock_create.assert_not_called()

    @patch(f"{SVC}.create_storefront")
    @patch(f"{SVC}.get_storefront_by_owner_id", return_value=None)
    def test_create_storefront_missing_brand_name(self, _existing, mock_create):
        self.log_in_as(OWNER_ID)
        res = self.client.post("/api/storefronts", json={})
        self.assertEqual(res.status_code, 400)
        self.assertIn("brand_name is required", res.get_json()["error"])
        mock_create.assert_not_called()

    @patch(f"{SVC}.create_storefront")
    @patch(f"{SVC}.get_storefront_by_owner_id", return_value=None)
    def test_create_storefront_blank_brand_name(self, _existing, mock_create):
        self.log_in_as(OWNER_ID)
        res = self.client.post("/api/storefronts", json={"brand_name": "   "})
        self.assertEqual(res.status_code, 400)
        self.assertIn("brand_name is required", res.get_json()["error"])
        mock_create.assert_not_called()

    @patch(f"{SVC}.create_storefront")
    @patch(f"{SVC}.get_storefront_by_owner_id", return_value=STOREFRONT)
    def test_create_storefront_only_one_per_user(self, _existing, mock_create):
        self.log_in_as(OWNER_ID)
        res = self.client.post("/api/storefronts", json={"brand_name": "Second Shop"})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json()["error"], "Storefront already created.")
        mock_create.assert_not_called()

    @patch(f"{SVC}.create_storefront")
    @patch(f"{SVC}.get_storefront_by_owner_id", return_value=None)
    def test_create_storefront_rejects_four_categories(self, _existing, mock_create):
        self.log_in_as(OWNER_ID)
        res = self.client.post("/api/storefronts",
                               json={"brand_name": "Kicks", "categories": "A,B,C,D"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("up to 3", res.get_json()["error"])
        mock_create.assert_not_called()

    @patch(f"{SVC}.create_storefront", return_value={"id": 5})
    @patch(f"{SVC}.get_storefront_by_owner_id", return_value=None)
    def test_create_storefront_removes_duplicate_categories(self, _existing, mock_create):
        self.log_in_as(OWNER_ID)
        res = self.client.post("/api/storefronts",
                               json={"brand_name": "Kicks", "categories": "Shoes, shoes, Hats"})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(mock_create.call_args.kwargs["categories"], "Shoes,Hats")


# ______________________________________________________________
# EDIT  -  PUT /api/storefronts/<id>
# ______________________________________________________________
class TestEditStorefront(BaseTest):

    @patch(f"{SVC}.update_storefront", return_value={"id": 5, "brand_name": "New Kicks"})
    @patch(f"{SVC}.get_storefront_by_id", return_value=STOREFRONT)
    def test_edit_storefront_success_as_owner(self, _get, mock_update):
        self.log_in_as(OWNER_ID)
        res = self.client.put("/api/storefronts/5", json={"brand_name": "  New Kicks  "})
        self.assertEqual(res.status_code, 200)
        kwargs = mock_update.call_args.kwargs
        self.assertEqual(kwargs["storefront_id"], 5)
        self.assertEqual(kwargs["brand_name"], "New Kicks")

    @patch(f"{SVC}.update_storefront")
    def test_edit_storefront_requires_login(self, mock_update):
        res = self.client.put("/api/storefronts/5", json={"brand_name": "New Kicks"})
        self.assertEqual(res.status_code, 401)
        mock_update.assert_not_called()

    @patch(f"{SVC}.update_storefront")
    @patch(f"{SVC}.get_storefront_by_id", return_value=STOREFRONT)
    def test_edit_storefront_wrong_user_forbidden(self, _get, mock_update):
        self.log_in_as(OTHER_ID)
        res = self.client.put("/api/storefronts/5", json={"brand_name": "Stolen"})
        self.assertEqual(res.status_code, 403)
        mock_update.assert_not_called()

    @patch(f"{SVC}.update_storefront", return_value={"id": 5, "brand_name": "Fixed"})
    @patch(f"{SVC}.get_storefront_by_id", return_value=STOREFRONT)
    def test_edit_storefront_admin_can_edit_any(self, _get, mock_update):
        self.log_in_as(OTHER_ID, role="admin")
        res = self.client.put("/api/storefronts/5", json={"brand_name": "Fixed"})
        self.assertEqual(res.status_code, 200)
        mock_update.assert_called_once()

    @patch(f"{SVC}.update_storefront")
    @patch(f"{SVC}.get_storefront_by_id", return_value=None)
    def test_edit_storefront_not_found(self, _get, mock_update):
        self.log_in_as(OWNER_ID)
        res = self.client.put("/api/storefronts/999", json={"brand_name": "Kicks"})
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.get_json()["error"], "Storefront not found.")
        mock_update.assert_not_called()

    @patch(f"{SVC}.update_storefront")
    @patch(f"{SVC}.get_storefront_by_id", return_value=STOREFRONT)
    def test_edit_storefront_blank_brand_name(self, _get, mock_update):
        self.log_in_as(OWNER_ID)
        res = self.client.put("/api/storefronts/5", json={"brand_name": "  "})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json()["error"], "brand_name cannot be empty.")
        mock_update.assert_not_called()

    @patch(f"{SVC}.update_storefront")
    @patch(f"{SVC}.get_storefront_by_id", return_value=STOREFRONT)
    def test_edit_storefront_rejects_four_categories(self, _get, mock_update):
        self.log_in_as(OWNER_ID)
        res = self.client.put("/api/storefronts/5", json={"categories": ["A", "B", "C", "D"]})
        self.assertEqual(res.status_code, 400)
        self.assertIn("up to 3", res.get_json()["error"])
        mock_update.assert_not_called()


# ______________________________________________________________
# DELETE  -  POST /storefronts/<id>/delete  (form route: redirects + flash)
# ______________________________________________________________
class TestDeleteStorefront(BaseTest):

    @patch(f"{SVC}.delete_storefront_permanently")
    @patch(f"{SVC}.get_storefront_by_id", return_value=STOREFRONT)
    def test_delete_storefront_success(self, _get, mock_delete):
        self.log_in_as(OWNER_ID)
        res = self.client.post("/storefronts/5/delete", data={"confirm_name": "Kicks"})
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers["Location"].endswith("/storefronts"))
        mock_delete.assert_called_once_with(5)
        category, message = self.flashes()[0]
        self.assertEqual(category, "success")
        self.assertIn("Kicks", message)

    @patch(f"{SVC}.delete_storefront_permanently")
    @patch(f"{SVC}.get_storefront_by_id", return_value=STOREFRONT)
    def test_delete_storefront_trims_typed_name(self, _get, mock_delete):
        self.log_in_as(OWNER_ID)
        self.client.post("/storefronts/5/delete", data={"confirm_name": "  Kicks  "})
        mock_delete.assert_called_once_with(5)

    @patch(f"{SVC}.delete_storefront_permanently")
    def test_delete_storefront_requires_login(self, mock_delete):
        res = self.client.post("/storefronts/5/delete", data={"confirm_name": "Kicks"})
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers["Location"].endswith("/auth/login"))
        mock_delete.assert_not_called()

    @patch(f"{SVC}.delete_storefront_permanently")
    @patch(f"{SVC}.get_storefront_by_id", return_value=STOREFRONT)
    def test_delete_storefront_wrong_user(self, _get, mock_delete):
        self.log_in_as(OTHER_ID)
        res = self.client.post("/storefronts/5/delete", data={"confirm_name": "Kicks"})
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers["Location"].endswith("/storefronts/5/edit"))
        category, message = self.flashes()[0]
        self.assertEqual(category, "error")
        self.assertIn("Only the owner", message)
        mock_delete.assert_not_called()

    @patch(f"{SVC}.delete_storefront_permanently")
    @patch(f"{SVC}.get_storefront_by_id", return_value=STOREFRONT)
    def test_delete_storefront_admin_not_owner_refused(self, _get, mock_delete):
        self.log_in_as(OTHER_ID, role="admin")
        res = self.client.post("/storefronts/5/delete", data={"confirm_name": "Kicks"})
        self.assertTrue(res.headers["Location"].endswith("/storefronts/5/edit"))
        self.assertIn("Only the owner", self.flashes()[0][1])
        mock_delete.assert_not_called()

    @patch(f"{SVC}.delete_storefront_permanently")
    @patch(f"{SVC}.get_storefront_by_id", return_value=STOREFRONT)
    def test_delete_storefront_name_mismatch(self, _get, mock_delete):
        self.log_in_as(OWNER_ID)
        res = self.client.post("/storefronts/5/delete", data={"confirm_name": "Kick"})
        self.assertTrue(res.headers["Location"].endswith("/storefronts/5/edit"))
        self.assertIn("does not match", self.flashes()[0][1])
        mock_delete.assert_not_called()

    @patch(f"{SVC}.delete_storefront_permanently")
    @patch(f"{SVC}.get_storefront_by_id", return_value=None)
    def test_delete_storefront_not_found(self, _get, mock_delete):
        self.log_in_as(OWNER_ID)
        res = self.client.post("/storefronts/999/delete", data={"confirm_name": "Kicks"})
        self.assertTrue(res.headers["Location"].endswith("/storefronts/999/edit"))
        self.assertEqual(self.flashes()[0][1], "Storefront not found.")
        mock_delete.assert_not_called()

    @patch(f"{SVC}.delete_storefront_permanently")
    def test_delete_storefront_get_not_allowed(self, mock_delete):
        self.log_in_as(OWNER_ID)
        res = self.client.get("/storefronts/5/delete")
        self.assertEqual(res.status_code, 405)
        mock_delete.assert_not_called()


# ______________________________________________________________
# UPLOAD  -  POST /api/storefronts/upload-image
# ______________________________________________________________
class TestUploadStorefrontImage(BaseTest):

    def _post_file(self, filename):
        return self.client.post(UPLOAD_URL, content_type="multipart/form-data",
                                data={"file": (BytesIO(b"fake image bytes"), filename)})

    @patch(S3_UPLOAD, return_value="https://bucket.test/storefronts/abc.png")
    def test_upload_image_success(self, mock_upload):
        self.log_in_as(OWNER_ID)
        res = self._post_file("logo.png")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {"url": "https://bucket.test/storefronts/abc.png"})
        self.assertEqual(mock_upload.call_args.kwargs["folder"], "storefronts")

    @patch(S3_UPLOAD, return_value="https://bucket.test/storefronts/abc.png")
    def test_upload_image_uppercase_extension_ok(self, mock_upload):
        self.log_in_as(OWNER_ID)
        res = self._post_file("LOGO.PNG")
        self.assertEqual(res.status_code, 200)
        mock_upload.assert_called_once()

    @patch(S3_UPLOAD)
    def test_upload_image_no_file(self, mock_upload):
        self.log_in_as(OWNER_ID)
        res = self.client.post(UPLOAD_URL, content_type="multipart/form-data", data={})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json()["error"], "No file provided")
        mock_upload.assert_not_called()

    @patch(S3_UPLOAD)
    def test_upload_image_wrong_type(self, mock_upload):
        self.log_in_as(OWNER_ID)
        res = self._post_file("notes.txt")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json()["error"], "Invalid file type")
        mock_upload.assert_not_called()

    @patch(S3_UPLOAD, return_value=None)
    def test_upload_image_s3_failure(self, _upload):
        self.log_in_as(OWNER_ID)
        res = self._post_file("logo.png")
        self.assertEqual(res.status_code, 500)
        self.assertEqual(res.get_json()["error"], "Upload failed")

    # EXPECTED TO FAIL until the route checks login (see Test Plan notes).
    @unittest.expectedFailure
    @patch(S3_UPLOAD, return_value="https://bucket.test/storefronts/abc.png")
    def test_upload_image_requires_login(self, mock_upload):
        res = self._post_file("logo.png")
        self.assertEqual(res.status_code, 401)
        mock_upload.assert_not_called()


if __name__ == "__main__":
    unittest.main()
