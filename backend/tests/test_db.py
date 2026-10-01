#By Ryan 2/27/2026
# changed lines  3-13 - Makena Jelks 9/30/26
import sys
import os

# lets python find backend/db.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db import get_connection

try:
    # Attempt to "knock on the door" of the RDS server
    conn = get_connection()

    print("SUCCESS: Your laptop is authorized. You have access to The Vault!")
    conn.close()
except Exception as e:
    print(f"CONNECTION FAILED: {e}")
