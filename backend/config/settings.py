import os


class Config:
    # added - ava: read the secret key from the environment
    SECRET_KEY = os.getenv("SECRET_KEY")
    DATABASE_URL = os.getenv("DATABASE_URL", "")