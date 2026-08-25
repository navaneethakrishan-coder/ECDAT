# Local installation

## Prerequisites

- Python 3.11 or later
- Node.js 20.9 or later

## Backend

From `backend`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
uvicorn main:app --reload --port 8000
```

Open `http://127.0.0.1:8000/docs` for the generated API documentation.

## Frontend

From `frontend`:

```powershell
npm install
npm run dev
```

Open `http://localhost:3000`.

## Checks

```powershell
# backend
cd backend
python -m pytest

# frontend
cd ..\frontend
npm run lint
npm run build
```
