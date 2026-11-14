import os


class Config:
    # added - ava: read the secret key from the environment
    SECRET_KEY = os.getenv("SECRET_KEY")
    # DATABASE_URL removed by Ava Bell 10/27/26 (HG-100): backend/db.py is the only database configuration
