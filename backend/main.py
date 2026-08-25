"""FastAPI entry point for the ECDAT backend."""

from fastapi import FastAPI

from api.router import api_router

app = FastAPI(
    title="ECDAT API",
    version="0.1.0",
    description="API foundation for the Explainable Cryptographic Discovery platform.",
)
app.include_router(api_router, prefix="/api/v1")
