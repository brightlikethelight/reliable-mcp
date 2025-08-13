#!/bin/bash

# MCP Reliability Lab Web Dashboard Startup Script

echo "Starting MCP Reliability Lab Web Dashboard..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3 to continue."
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "Node.js is not installed. Please install Node.js to continue."
    exit 1
fi

# Start the backend
echo "Starting FastAPI backend..."
cd backend
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
echo "Installing backend dependencies..."
pip install -r requirements.txt

# Start backend in background
echo "Starting backend server on http://localhost:8000"
python main.py &
BACKEND_PID=$!

# Start the frontend
echo "Starting Next.js frontend..."
cd ../frontend

if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

echo "Starting frontend server on http://localhost:3000"
npm run dev &
FRONTEND_PID=$!

echo "======================================="
echo "MCP Reliability Lab is running!"
echo "======================================="
echo "Backend API: http://localhost:8000"
echo "Frontend UI: http://localhost:3000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"
echo "======================================="

# Function to handle cleanup on exit
cleanup() {
    echo "Stopping services..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "Services stopped."
    exit 0
}

# Set up trap to catch Ctrl+C
trap cleanup INT

# Wait for processes
wait