"""
return_controller.py

Routes for the returns page and return request submission.
"""

from flask import Blueprint, jsonify, render_template, request, redirect, url_for, session
from utils.auth_utils import get_current_user # I3 - Makena Jelks

from services.return_service import create_return_service, fetch_my_returns_service

returns_bp = Blueprint("returns_bp", __name__)


# HG-119 (Mattie Edozie, I4): list the logged-in user's own returns.
# The user comes from the session only, never from a request header.
@returns_bp.get("/returns/my")
def my_returns():
    current_user = get_current_user()
    if current_user is None:
        return jsonify({"error": "Unauthorized."}), 401

    try:
        return jsonify(fetch_my_returns_service(current_user)), 200
    except Exception:
        return jsonify({"error": "Could not load your returns."}), 500


@returns_bp.get("/returns")
def returns_page():
    if "user" not in session:
        return redirect(url_for("auth.login"))
    return render_template("returns.html")


@returns_bp.post("/returns")
def submit_return():
    current_user = get_current_user()
    if current_user is None:
        return jsonify({"error": "Unauthorized."}), 401

    data = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})
    damage_image_url = None

    if "damage_image" in request.files and request.files["damage_image"].filename:
        from utils.s3 import upload_image_to_s3

        file = request.files["damage_image"]
        if not file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            return jsonify({"error": "Damage image must be PNG, JPG, JPEG, GIF, or WebP."}), 400

        damage_image_url = upload_image_to_s3(file, folder="returns/damage")
        if not damage_image_url:
            return jsonify({"error": "Damage image upload failed."}), 500

    try:
        created = create_return_service(current_user, data, damage_image_url=damage_image_url)
        return jsonify(created), 201
    except Exception as e:
        message = str(e)
        if "unauthorized" in message.lower():
            return jsonify({"error": message}), 401
        return jsonify({"error": message}), 400
