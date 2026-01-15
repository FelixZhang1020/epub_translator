#!/bin/bash

# ePub Translator - Start Script
# Starts both backend and frontend servers with configurable ports

set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Default ports (can be overridden by .env files)
BACKEND_PORT=${PORT:-8000}
FRONTEND_PORT=${VITE_PORT:-5173}

# Load backend .env if exists
if [ -f "$SCRIPT_DIR/backend/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/backend/.env" | xargs)
    BACKEND_PORT=${PORT:-8000}
fi

# Load frontend .env if exists
if [ -f "$SCRIPT_DIR/frontend/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/frontend/.env" | xargs)
    FRONTEND_PORT=${VITE_PORT:-5173}
fi

echo "=========================================="
echo "   ePub Translator - Starting..."
echo "=========================================="
echo ""
echo "Configuration:"
echo "  Backend Port:  $BACKEND_PORT"
echo "  Frontend Port: $FRONTEND_PORT"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is not installed"
    exit 1
fi

# Backend setup
echo "Setting up backend..."
cd "$SCRIPT_DIR/backend"

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies if needed
if [ ! -f "venv/.deps_installed" ]; then
    echo "Installing Python dependencies..."
    pip install -q -r requirements.txt
    touch venv/.deps_installed
fi

# Frontend setup
echo "Setting up frontend..."
cd "$SCRIPT_DIR/frontend"

# Install npm dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing npm dependencies..."
    npm install
fi

# Start servers
echo ""
echo "=========================================="
echo "   Starting servers..."
echo "=========================================="
echo ""
echo "Backend:  http://localhost:$BACKEND_PORT"
echo "Frontend: http://localhost:$FRONTEND_PORT"
echo "API Docs: http://localhost:$BACKEND_PORT/docs"
echo ""
echo "Press Ctrl+C to stop both servers"
echo "=========================================="
echo ""

# Start backend in background
cd "$SCRIPT_DIR/backend"
source venv/bin/activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port $BACKEND_PORT &
BACKEND_PID=$!

# Wait for backend to start
sleep 2

# Start frontend
cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

# Handle shutdown
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Wait for processes
wait

