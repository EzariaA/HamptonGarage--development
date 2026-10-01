# Makena Jelks worked on the changes for this code

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    #connect the databases using the setting from .env
    #if a setting is missing, it will use the local default instead of AWS
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode=os.getenv("DB_SSLMODE", "prefer"),
    )
    
