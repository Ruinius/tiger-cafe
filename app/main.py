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
    documents,
    historical_calculations,
    income_statement,
)

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
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(balance_sheet.router, prefix="/api/documents", tags=["balance-sheet"])
app.include_router(income_statement.router, prefix="/api/documents", tags=["income-statement"])
app.include_router(
    historical_calculations.router, prefix="/api/documents", tags=["historical-calculations"]
)


@app.get("/")
async def root():
    return {"message": "Tiger-Cafe API", "version": "0.1.0"}


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}
