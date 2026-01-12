"""
Seed script for development data.
Run this manually: python seed_dev_data.py
Logic is now centralized in app.db.init_db
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.db.init_db import init_db

if __name__ == "__main__":
    print("Running manual seed...")
    db = SessionLocal()
    try:
        init_db(db)
        print("Manual seed complete.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()
