import os


class Config:
    # added - ava: load secret key from environment without a hardcoded fallback
    SECRET_KEY = os.getenv("SECRET_KEY")
    DATABASE_URL = os.getenv("DATABASE_URL", "")