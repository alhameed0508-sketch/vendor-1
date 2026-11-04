#!/usr/bin/env bash
# MuleCatch Development Startup Script
# Starts both backend (port 8000) and frontend (port 3000) in parallel.
# The frontend CRA proxy forwards /api/* to the backend automatically.
#
# Prerequisites:
#   - Python 3.10+ with pip
#   - Node.js 18+ with npm
#   - Copy .env.example to backend/.env (adjust values as needed)
#
# Usage:
#   chmod +x scripts/start-dev.sh
#   ./scripts/start-dev.sh

set -e

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== MuleCatch Dev Startup ==="
echo ""

# Check backend .env exists
if [ ! -f "$ROOT_DIR/backend/.env" ]; then
  echo "[!] backend/.env not found. Copying from .env.example..."
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/backend/.env"
  echo "    Created backend/.env with demo defaults."
  echo ""
fi

# Install backend deps if needed
if [ ! -d "$ROOT_DIR/backend/__pycache__" ] && [ ! -f "$ROOT_DIR/backend/.deps-installed" ]; then
  echo "[1/4] Installing backend dependencies..."
  pip install -r "$ROOT_DIR/backend/requirements.txt" -q
  touch "$ROOT_DIR/backend/.deps-installed"
else
  echo "[1/4] Backend dependencies OK"
fi

# Install frontend deps if needed
if [ ! -d "$ROOT_DIR/frontend/node_modules" ]; then
  echo "[2/4] Installing frontend dependencies..."
  cd "$ROOT_DIR/frontend" && npm install --legacy-peer-deps
else
  echo "[2/4] Frontend dependencies OK"
fi

echo "[3/4] Starting backend on http://localhost:8000 ..."
cd "$ROOT_DIR/backend"
PYTHONPATH="$ROOT_DIR" python -m uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

echo "[4/4] Starting frontend on http://localhost:3000 ..."
cd "$ROOT_DIR/frontend"
npm start &
FRONTEND_PID=$!

echo ""
echo "=== Both servers starting ==="
echo "  Backend:  http://localhost:8000  (PID $BACKEND_PID)"
echo "  Frontend: http://localhost:3000  (PID $FRONTEND_PID)"
echo ""
echo "  Frontend proxies /api/* to backend automatically."
echo "  Login: investigator / iob@2024"
echo ""
echo "  Press Ctrl+C to stop both."

# Trap Ctrl+C to kill both
trap "echo ''; echo 'Shutting down...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

wait
