#!/usr/bin/env python3
"""Run the minimal API server."""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "web" / "backend"))

if __name__ == "__main__":
    import uvicorn
    from api.minimal import app
    
    print("Starting Minimal MCP API on http://localhost:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)