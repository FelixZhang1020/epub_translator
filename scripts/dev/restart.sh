#!/bin/bash

# Restart ePub Translate Services

PROJECT_ROOT="/Users/felixzhang/VibeCoding/epub_translator"

# Default ports
BACKEND_PORT=8000
FRONTEND_PORT=5173

# Load backend .env if exists
if [ -f "$PROJECT_ROOT/backend/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/backend/.env" | grep -v '^$' | xargs)
    BACKEND_PORT=${PORT:-8000}
    FRONTEND_PORT=${FRONTEND_PORT:-5173}
fi

# Load frontend .env if exists
if [ -f "$PROJECT_ROOT/frontend/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/frontend/.env" | grep -v '^$' | xargs)
    FRONTEND_PORT=${VITE_PORT:-$FRONTEND_PORT}
fi

echo "Stopping services..."
pkill -f "uvicorn app.main:app" || true
pkill -f "vite" || true
sleep 1

echo "Starting backend on port $BACKEND_PORT..."
cd "$PROJECT_ROOT/backend"
source venv/bin/activate
nohup uvicorn app.main:app --reload --host 0.0.0.0 --port $BACKEND_PORT > /dev/null 2>&1 &
echo "Backend started"

sleep 2

echo "Starting frontend on port $FRONTEND_PORT..."
cd "$PROJECT_ROOT/frontend"
nohup npm run dev > /dev/null 2>&1 &
echo "Frontend started"

echo ""
echo "Services restarted!"
echo "Backend:  http://localhost:$BACKEND_PORT"
echo "Frontend: http://localhost:$FRONTEND_PORT"

