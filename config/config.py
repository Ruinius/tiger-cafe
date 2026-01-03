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

# Google OAuth
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tiger_cafe.db")

# Data sources
DATA_CACHE_DIR = "data/cache"
DATA_STORAGE_DIR = "data/storage"
UPLOAD_DIR = "data/uploads"  # Directory for uploaded PDF files

# Agent settings - Gemini with very low temperature for consistent analysis
DEFAULT_MODEL = "gemini-2.5-flash-lite"  # or "gemini-pro" for earlier version
TEMPERATURE = 0.1  # Very low temperature for focused, deterministic responses
EMBEDDING_MODEL = "models/embedding-001"  # Gemini embedding model

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "logs/tiger-cafe.log"

# Environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")  # "development" or "production"
DEBUG = (
    os.getenv("DEBUG", "true" if ENVIRONMENT == "development" else "false").lower() == "true"
)  # Enable test endpoints in development
