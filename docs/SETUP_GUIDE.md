# Setup Guide

This guide will help you set up the Tiger-Cafe application for development.

## Prerequisites

- Python 3.8 or higher
- Git (for version control)
- Google Cloud Platform account (for OAuth credentials)
- Google AI Studio account (for Gemini API key)

## Initial Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd tiger-cafe
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root (you can copy from `keys.example.txt`):

```bash
GEMINI_API_KEY=your-gemini-api-key-here
GOOGLE_CLIENT_ID=your-google-client-id-here
GOOGLE_CLIENT_SECRET=your-google-client-secret-here
```

#### Getting API Keys:

1. **Gemini API Key**:
   - Go to https://makersuite.google.com/app/apikey
   - Create a new API key
   - Copy it to your `.env` file

2. **Google OAuth Credentials**:
   - Go to https://console.cloud.google.com/apis/credentials
   - Create a new OAuth 2.0 Client ID
   - Set authorized redirect URIs (e.g., `http://localhost:8000/api/auth/callback`)
   - Copy the Client ID and Client Secret to your `.env` file

### 5. Create Required Directories

```bash
mkdir -p data/cache
mkdir -p data/storage
mkdir -p data/uploads
mkdir -p logs
```

### 6. Initialize Database

The database will be automatically created when you first run the application. The SQLite database file will be created at `tiger_cafe.db` in the project root.

## Running the Application

### Development Server

```bash
python run.py
```

Or using uvicorn directly:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Alternative API Documentation: http://localhost:8000/redoc

## Project Structure

See [README.md](../README.md) for the complete project structure.

## Database Schema

See [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) for detailed database schema documentation.

## Next Steps

1. Set up your frontend (when ready)
2. Implement document upload functionality (Phase 2)
3. Build document classification agents
4. Implement financial analysis agents

## Troubleshooting

### Database Issues

If you need to reset the database:

```bash
# Delete the database file
rm tiger_cafe.db  # On Windows: del tiger_cafe.db

# Restart the application (database will be recreated)
python run.py
```

### Authentication Issues

- Ensure your Google OAuth credentials are correctly set in `.env`
- Check that authorized redirect URIs match your application URLs
- Verify that the GOOGLE_CLIENT_ID matches your OAuth client configuration

### Import Errors

If you encounter import errors, make sure:
- Your virtual environment is activated
- All dependencies are installed: `pip install -r requirements.txt`
- You're running commands from the project root directory

