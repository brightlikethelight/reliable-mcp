#!/bin/bash
# Run script for MCP Reliability Lab Web UI

echo "=========================================="
echo "MCP Reliability Lab - Web UI"
echo "=========================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
echo "Installing requirements..."
pip install -q -r requirements_web.txt

# Create necessary directories
mkdir -p templates/partials
mkdir -p static

echo ""
echo "Starting Web UI..."
echo "=========================================="
echo "Open your browser and navigate to:"
echo "  http://localhost:8000"
echo "=========================================="
echo ""

# Run the web UI
python web_ui.py