"""
Example configuration file.
Copy this to config.py and update with your actual values.
"""

# API Keys - Load from environment or .env file
# Set GEMINI_API_KEY in your .env file (see .env.example)
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Data sources
DATA_CACHE_DIR = "data/cache"
DATA_STORAGE_DIR = "data/storage"

# Agent settings - Gemini with very low temperature for consistent analysis
DEFAULT_MODEL = "gemini-2.5-flash-lite"  # or "gemini-pro" for earlier version
TEMPERATURE = 0.1  # Very low temperature for focused, deterministic responses

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "logs/tiger-cafe.log"

