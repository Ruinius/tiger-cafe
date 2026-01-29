"""
Main FastAPI application entry point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import (
    auth,
    balance_sheet,
    companies,
    dashboard,
    documents,
    extraction_tasks,
    historical_calculations,
    income_statement,
    processing,
    qualitative,
    status_stream,
)
from app.utils.cleanup_scheduler import get_cleanup_scheduler

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Tiger-Cafe", description="AI agents for equity investment analysis", version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],  # Adjust as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(companies.router, prefix="/api/companies", tags=["companies"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(qualitative.router, prefix="/api/companies", tags=["companies"])
# Specific routers must effectively precede generic /{document_id} routes
app.include_router(status_stream.router, prefix="/api/documents", tags=["status-stream"])
app.include_router(processing.router, prefix="/api/processing", tags=["processing"])
app.include_router(balance_sheet.router, prefix="/api/documents", tags=["balance-sheet"])
app.include_router(income_statement.router, prefix="/api/documents", tags=["income-statement"])
app.include_router(extraction_tasks.router, prefix="/api/documents", tags=["extraction-tasks"])
app.include_router(
    historical_calculations.router, prefix="/api/documents", tags=["historical-calculations"]
)
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])


@app.get("/")
async def root():
    return {"message": "Tiger-Cafe API", "version": "0.1.0"}


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    # Start cleanup scheduler
    get_cleanup_scheduler()
    print("[Startup] Cleanup scheduler initialized")

    # Seed Dev User & Data
    from app.database import SessionLocal
    from app.db.init_db import init_db

    db = SessionLocal()
    try:
        init_db(db)
        print("[Startup] Database initialization complete")
    except Exception as e:
        print(f"[Startup] Error initializing database: {e}")
    finally:
        db.close()


@app.on_event("shutdown")
def shutdown_event():
    """Gracefully shut down services."""
    import sys

    # Shut down queue worker if initialized
    if "app.services.queue_service" in sys.modules:
        from app.services.queue_service import queue_service

        queue_service.shutdown()

    # Shut down cleanup scheduler
    from app.utils.cleanup_scheduler import cleanup_scheduler

    if cleanup_scheduler:
        try:
            cleanup_scheduler.shutdown()
            print("[Shutdown] Cleanup scheduler stopped")
        except Exception as e:
            print(f"[Shutdown] Scheduler shutdown skipped: {e}")
