#!/bin/bash
# MCP Reliability Lab - One-Command Installer
# Installs everything needed to run the MCP Reliability Lab

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Banner
echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════╗"
echo "║     🔬 MCP Reliability Lab Installer 🔬      ║"
echo "║         Scientific Testing for MCP           ║"
echo "╚══════════════════════════════════════════════╝"
echo -e "${NC}"

# Check OS
OS="Unknown"
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="Linux"
else
    echo -e "${RED}❌ Unsupported OS: $OSTYPE${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Detected OS: $OS${NC}"

# Check prerequisites
check_requirement() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}❌ $1 is required but not installed${NC}"
        echo -e "${YELLOW}   Please install $1 and run this script again${NC}"
        
        # Provide installation hints
        case $1 in
            python3)
                echo "   Install Python 3: https://www.python.org/downloads/"
                ;;
            npm)
                echo "   Install Node.js: https://nodejs.org/"
                ;;
            git)
                echo "   Install Git: https://git-scm.com/"
                ;;
            sqlite3)
                if [[ "$OS" == "macOS" ]]; then
                    echo "   Install with: brew install sqlite"
                else
                    echo "   Install with: sudo apt-get install sqlite3"
                fi
                ;;
        esac
        exit 1
    fi
    echo -e "${GREEN}✅ $1 found$(command -v $1)${NC}"
}

echo -e "\n${BLUE}Checking prerequisites...${NC}"
check_requirement python3
check_requirement npm
check_requirement git
check_requirement sqlite3

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.8"
if [[ $(echo "$PYTHON_VERSION $REQUIRED_VERSION" | awk '{print ($1 >= $2)}') -eq 0 ]]; then
    echo -e "${RED}❌ Python $REQUIRED_VERSION or higher required (found $PYTHON_VERSION)${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python version: $PYTHON_VERSION${NC}"

# Set installation directory
DEFAULT_DIR="$HOME/mcp-reliability-lab"
echo -e "\n${BLUE}Installation directory [${DEFAULT_DIR}]:${NC} "
read -r CUSTOM_DIR
INSTALL_DIR="${CUSTOM_DIR:-$DEFAULT_DIR}"

# Create directory
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}⚠️  Directory exists. Overwrite? (y/n):${NC} "
    read -r OVERWRITE
    if [ "$OVERWRITE" != "y" ]; then
        echo "Installation cancelled"
        exit 0
    fi
    rm -rf "$INSTALL_DIR"
fi

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Download or copy files
echo -e "\n${BLUE}📦 Installing MCP Reliability Lab...${NC}"

# Check if we're running from the source directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
if [ -f "$SCRIPT_DIR/web_ui.py" ]; then
    echo "Installing from local source..."
    cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"
else
    # Download from GitHub (when available)
    echo "Downloading from repository..."
    git clone https://github.com/yourusername/mcp-reliability-lab.git . 2>/dev/null || {
        echo -e "${YELLOW}Repository not available, using local files${NC}"
        cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"
    }
fi

# Create virtual environment
echo -e "\n${BLUE}🐍 Setting up Python environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo -e "${BLUE}📦 Installing Python dependencies...${NC}"
pip install --upgrade pip > /dev/null 2>&1

# Create comprehensive requirements file if it doesn't exist
if [ ! -f requirements.txt ]; then
    cat > requirements.txt << 'EOF'
# Core dependencies
mcp>=0.1.0
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
httpx>=0.24.0
jinja2>=3.1.0
python-multipart>=0.0.6

# Testing dependencies
hypothesis>=6.80.0
pytest>=7.4.0
pytest-asyncio>=0.21.0

# Optional but recommended
aiofiles>=23.2.0
EOF
fi

pip install -q -r requirements.txt

# Install MCP servers
echo -e "\n${BLUE}🔧 Installing MCP servers...${NC}"
npm install -g @modelcontextprotocol/server-filesystem 2>/dev/null || {
    echo -e "${YELLOW}Note: MCP filesystem server may require sudo${NC}"
}

# Initialize database
echo -e "\n${BLUE}💾 Initializing databases...${NC}"
cat > init_database.py << 'EOF'
#!/usr/bin/env python3
"""Initialize all databases for MCP Reliability Lab."""

import sqlite3
from pathlib import Path

databases = [
    "mcp_test.db",
    "scientific_metrics.db",
    "benchmark_results.db",
    "leaderboard.db",
    "web_metrics.db"
]

for db_name in databases:
    conn = sqlite3.connect(db_name)
    conn.execute("CREATE TABLE IF NOT EXISTS info (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT OR REPLACE INTO info VALUES ('initialized', datetime('now'))")
    conn.commit()
    conn.close()
    print(f"  ✓ {db_name}")

print("Databases initialized successfully!")
EOF

python3 init_database.py

# Create start script
echo -e "\n${BLUE}📝 Creating start scripts...${NC}"
cat > start.sh << 'EOF'
#!/bin/bash
# Start MCP Reliability Lab

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Activate virtual environment
source venv/bin/activate

# Check if port 8000 is available
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "Port 8000 is already in use. Please stop the existing service."
    exit 1
fi

echo -e "${BLUE}🚀 Starting MCP Reliability Lab...${NC}"
echo -e "${GREEN}   Open your browser at: http://localhost:8000${NC}"
echo -e "${GREEN}   Press Ctrl+C to stop${NC}"
echo ""

# Start the web UI
python web_ui.py
EOF
chmod +x start.sh

# Create CLI script
cat > mcp-lab << 'EOF'
#!/usr/bin/env python3
"""MCP Reliability Lab CLI."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cli import main

if __name__ == "__main__":
    main()
EOF
chmod +x mcp-lab

# Create systemd service (Linux only)
if [[ "$OS" == "Linux" ]]; then
    echo -e "\n${BLUE}Creating systemd service...${NC}"
    cat > mcp-reliability-lab.service << EOF
[Unit]
Description=MCP Reliability Lab
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/web_ui.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
    
    echo -e "${YELLOW}To install as a system service:${NC}"
    echo "  sudo cp mcp-reliability-lab.service /etc/systemd/system/"
    echo "  sudo systemctl enable mcp-reliability-lab"
    echo "  sudo systemctl start mcp-reliability-lab"
fi

# Create uninstall script
cat > uninstall.sh << EOF
#!/bin/bash
echo "Uninstalling MCP Reliability Lab..."
rm -rf "$INSTALL_DIR"
echo "✅ Uninstalled successfully"
EOF
chmod +x uninstall.sh

# Installation complete
echo -e "\n${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     ✅ Installation Complete! ✅              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Installation location:${NC} $INSTALL_DIR"
echo ""
echo -e "${BLUE}To start MCP Reliability Lab:${NC}"
echo "  cd $INSTALL_DIR"
echo "  ./start.sh"
echo ""
echo -e "${BLUE}To use the CLI:${NC}"
echo "  cd $INSTALL_DIR"
echo "  ./mcp-lab --help"
echo ""
echo -e "${BLUE}To uninstall:${NC}"
echo "  $INSTALL_DIR/uninstall.sh"
echo ""
echo -e "${GREEN}Enjoy testing your MCP servers! 🔬${NC}"