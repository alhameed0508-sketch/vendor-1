@echo off
REM MuleCatch Development Startup Script (Windows)
REM Starts both backend (port 8000) and frontend (port 3000).
REM The frontend CRA proxy forwards /api/* to the backend automatically.
REM
REM Prerequisites:
REM   - Python 3.10+ with pip
REM   - Node.js 18+ with npm
REM   - Copy .env.example to backend\.env (adjust values as needed)
REM
REM Usage:
REM   scripts\start-dev.bat

echo === MuleCatch Dev Startup ===
echo.

REM Check backend .env exists
if not exist "backend\.env" (
    echo [!] backend\.env not found. Copying from .env.example...
    copy ".env.example" "backend\.env" >nul
    echo     Created backend\.env with demo defaults.
    echo.
)

REM Install frontend deps if needed
if not exist "frontend\node_modules" (
    echo [1/3] Installing frontend dependencies...
    cd frontend && npm install --legacy-peer-deps && cd ..
) else (
    echo [1/3] Frontend dependencies OK
)

echo [2/3] Starting backend on http://localhost:8000 ...
start "MuleCatch Backend" cmd /c "cd backend && set PYTHONPATH=%cd%\.. && python -m uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload"

echo [3/3] Starting frontend on http://localhost:3000 ...
start "MuleCatch Frontend" cmd /c "cd frontend && npm start"

echo.
echo === Both servers starting ===
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo.
echo   Frontend proxies /api/* to backend automatically.
echo   Login: investigator / iob@2024
echo.
echo   Close the terminal windows to stop servers.
