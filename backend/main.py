from fastapi import FastAPI

app = FastAPI(
    title="ECDAT",
    description="Enterprise Cryptographic Discovery & Analysis Tool",
    version="0.1.0"
)


@app.get("/")
def root():
    return {
        "project": "ECDAT",
        "status": "running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }