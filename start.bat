@echo off
setlocal
title NEXUS ARENA OS
color 0B

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║                                                  ║
echo  ║           NEXUS ARENA OS  v3.0                  ║
echo  ║     Multi-Agent Crowd Intelligence Platform      ║
echo  ║                                                  ║
echo  ╚══════════════════════════════════════════════════╝
echo.

REM ── Check Python ────────────────────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python not found. Please install Python 3.10+ from python.org
    pause
    exit /b 1
)

echo  [1/3]  Installing backend dependencies...
pip install -r backend\requirements.txt -q --disable-pip-version-check
if %errorlevel% neq 0 (
    echo  [ERROR] pip install failed. Check your internet connection.
    pause
    exit /b 1
)

echo  [2/3]  Initializing database and seeding data...
python -c "from backend.database import init_db, seed_data; init_db(); seed_data()"
if %errorlevel% neq 0 (
    echo  [WARN]  DB init returned an error, continuing anyway...
)

echo  [3/3]  Starting Nexus Arena OS server...
echo.
echo  ┌─────────────────────────────────────────────────────┐
echo  │   Open your browser at:  http://localhost:8000      │
echo  │                                                     │
echo  │   Employee Login:  admin@nexus.com / NexusAdmin123  │
echo  │   Ticket Demo:     TKT-001 through TKT-010          │
echo  └─────────────────────────────────────────────────────┘
echo.

REM Open browser after a short delay
start "" timeout /t 2 /nobreak >nul & start http://localhost:8000

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

pause
