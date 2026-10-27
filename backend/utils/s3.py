# utils/s3.py
# The Vault Campus Marketplace
# Created by Day Ekoi - Iteration 5 4/10/26
# Handles all S3 image upload functionality

import boto3
import os
import uuid
from dotenv import load_dotenv
import logging  # added - ava
logger = logging.getLogger(__name__)  # added - ava

load_dotenv()

# S3 client setup
s3_client = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION", "us-east-2")
)

BUCKET_NAME = os.getenv("AWS_S3_BUCKET")
REGION = os.getenv("AWS_REGION", "us-east-2")


def upload_image_to_s3(file, folder="uploads"):
       """
       Uploads an image and returns its URL.
       If S3 isn't configured (local dev), saves to static/uploads/ instead.
       """
       try:
           ext = file.filename.rsplit(".", 1)[-1].lower()
           filename = f"{folder}/{uuid.uuid4().hex}.{ext}"

           # Local fallback - Hampton Garage Iteration 2
           if not BUCKET_NAME:
               root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "static", "uploads"))
               path = os.path.join(root, filename)
               os.makedirs(os.path.dirname(path), exist_ok=True)
               file.save(path)
               return f"/static/uploads/{filename}"

           s3_client.upload_fileobj(
               file,
               BUCKET_NAME,
               filename,
               ExtraArgs={"ContentType": file.content_type}
           )
           return f"https://{BUCKET_NAME}.s3.{REGION}.amazonaws.com/{filename}"

       except Exception as e:
                logger.error(f"Image upload error (bucket={BUCKET_NAME!r}, region={REGION!r}): {e}")  # added - ava # added - ava
                return None