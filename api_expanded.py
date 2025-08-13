#!/usr/bin/env python3
"""
Expanded API - Building incrementally from the working minimal base.
Adding ONE endpoint at a time and testing before moving on.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import asyncio
import sqlite3
import json
import time
from datetime import datetime
from pathlib import Path
import logging
import sys

# Add path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import our MCP client
from mcp_client import MCPClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Expanded MCP API",
    description="Incrementally expanded API with test execution capabilities",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request models
class TestConfig(BaseModel):
    """Configuration for a single test."""
    tool: str
    args: Dict[str, Any]
    expected_status: str = "success"
    timeout_ms: int = 5000

class TestSuite(BaseModel):
    """Configuration for a test suite."""
    name: str
    tests: List[TestConfig]

class TestResult(BaseModel):
    """Result from a test execution."""
    test_name: str
    tool: str
    status: str
    duration_ms: float
    result: Optional[Dict] = None
    error: Optional[str] = None
    timestamp: datetime

# Global client instance
mcp_client: Optional[MCPClient] = None

# Initialize test results database
def init_test_db():
    """Create test results table."""
    conn = sqlite3.connect('test_results.db')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_name TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            status TEXT NOT NULL,
            duration_ms REAL,
            result TEXT,
            error_msg TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("Test results database initialized")

@app.on_event("startup")
async def startup_event():
    """Initialize MCP client and database on startup."""
    global mcp_client
    try:
        # Initialize database
        init_test_db()
        
        # Connect MCP client
        mcp_client = MCPClient()
        await mcp_client.connect_filesystem("/private/tmp")
        logger.info("MCP client connected successfully")
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        mcp_client = None

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    global mcp_client
    if mcp_client:
        await mcp_client.close()
        logger.info("MCP client closed")

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Expanded MCP API",
        "version": "2.0.0",
        "endpoints": {
            "/health": "Health check",
            "/run-test": "Run a single test",
            "/run-test-suite": "Run a test suite",
            "/test-results": "Get test results",
            "/metrics": "Get performance metrics"
        }
    }

@app.get("/health")
async def health():
    """Health check."""
    if not mcp_client or not mcp_client.connected:
        raise HTTPException(status_code=503, detail="MCP client not connected")
    
    tools = await mcp_client.list_tools()
    return {
        "status": "healthy",
        "mcp": "connected",
        "available_tools": len(tools.get("result", {}).get("tools", []))
    }

# Phase 1.3: Add test execution endpoint
@app.post("/run-test")
async def run_test(test_config: TestConfig) -> TestResult:
    """Run a single test - BUILD ON WORKING /test-mcp endpoint."""
    if not mcp_client or not mcp_client.connected:
        raise HTTPException(status_code=503, detail="MCP client not connected")
    
    start_time = time.time()
    status = "success"
    result = None
    error_msg = None
    
    try:
        # Use the retry functionality we just added
        result = await mcp_client.call_tool_with_retry(
            test_config.tool,
            test_config.args,
            retries=3
        )
        
        # Verify result structure
        if "result" not in result:
            status = "failed"
            error_msg = "No result in response"
        
    except asyncio.TimeoutError:
        status = "timeout"
        error_msg = f"Test timed out after {test_config.timeout_ms}ms"
    except Exception as e:
        status = "failed"
        error_msg = str(e)
    
    duration_ms = (time.time() - start_time) * 1000
    
    # Store in database
    conn = sqlite3.connect('test_results.db')
    conn.execute('''
        INSERT INTO test_results (test_name, tool_name, status, duration_ms, result, error_msg)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        f"{test_config.tool}_test",
        test_config.tool,
        status,
        duration_ms,
        json.dumps(result) if result else None,
        error_msg
    ))
    conn.commit()
    conn.close()
    
    return TestResult(
        test_name=f"{test_config.tool}_test",
        tool=test_config.tool,
        status=status,
        duration_ms=duration_ms,
        result=result,
        error=error_msg,
        timestamp=datetime.now()
    )

# Phase 1.4: Add test suite endpoint
@app.post("/run-test-suite")
async def run_test_suite(suite: TestSuite) -> Dict:
    """Run multiple tests - ONLY after single test works."""
    if not mcp_client or not mcp_client.connected:
        raise HTTPException(status_code=503, detail="MCP client not connected")
    
    results = []
    suite_start = time.time()
    
    for test_config in suite.tests:
        # Reuse the working single test endpoint
        result = await run_test(test_config)
        results.append(result.dict())
    
    suite_duration = (time.time() - suite_start) * 1000
    
    # Calculate summary statistics
    total_tests = len(results)
    passed_tests = sum(1 for r in results if r["status"] == "success")
    failed_tests = sum(1 for r in results if r["status"] == "failed")
    
    return {
        "suite_name": suite.name,
        "total_tests": total_tests,
        "passed": passed_tests,
        "failed": failed_tests,
        "duration_ms": suite_duration,
        "results": results
    }

@app.get("/test-results")
async def get_test_results(limit: int = 10):
    """Get recent test results from database."""
    conn = sqlite3.connect('test_results.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT test_name, tool_name, status, duration_ms, error_msg, timestamp
        FROM test_results
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (limit,))
    
    results = []
    for row in cursor.fetchall():
        results.append({
            "test_name": row[0],
            "tool_name": row[1],
            "status": row[2],
            "duration_ms": row[3],
            "error": row[4],
            "timestamp": row[5]
        })
    
    conn.close()
    return {"results": results}

@app.get("/metrics")
async def get_metrics():
    """Get performance metrics."""
    if not mcp_client:
        raise HTTPException(status_code=503, detail="MCP client not connected")
    
    return mcp_client.get_metrics_summary()


# Test script to verify the API works
async def test_expanded_api():
    """Test the expanded API endpoints."""
    import httpx
    
    print("=" * 60)
    print("TESTING EXPANDED API")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        base_url = "http://localhost:8002"
        
        # Test 1: Health check
        print("\nTest 1: Health Check")
        response = await client.get(f"{base_url}/health")
        assert response.status_code == 200
        print(f"✅ Health check: {response.json()}")
        
        # Test 2: Run single test
        print("\nTest 2: Run Single Test")
        response = await client.post(f"{base_url}/run-test", json={
            "tool": "write_file",
            "args": {
                "path": "/private/tmp/api_test.txt",
                "content": "Testing expanded API"
            }
        })
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"
        print(f"✅ Single test executed: {result['tool']} - {result['status']}")
        
        # Test 3: Run test suite
        print("\nTest 3: Run Test Suite")
        response = await client.post(f"{base_url}/run-test-suite", json={
            "name": "Basic MCP Operations",
            "tests": [
                {
                    "tool": "list_tools",
                    "args": {}
                },
                {
                    "tool": "write_file",
                    "args": {
                        "path": "/private/tmp/suite_test.txt",
                        "content": "Suite test"
                    }
                },
                {
                    "tool": "read_text_file",
                    "args": {
                        "path": "/private/tmp/suite_test.txt"
                    }
                }
            ]
        })
        assert response.status_code == 200
        suite_result = response.json()
        print(f"✅ Test suite executed: {suite_result['passed']}/{suite_result['total_tests']} passed")
        
        # Test 4: Get test results
        print("\nTest 4: Get Test Results")
        response = await client.get(f"{base_url}/test-results?limit=5")
        assert response.status_code == 200
        results = response.json()
        print(f"✅ Retrieved {len(results['results'])} test results")
        
        # Test 5: Get metrics
        print("\nTest 5: Get Metrics")
        response = await client.get(f"{base_url}/metrics")
        assert response.status_code == 200
        metrics = response.json()
        print(f"✅ Metrics: {metrics['overall']['total_calls']} total calls")
    
    print("\n" + "=" * 60)
    print("✅ ALL API ENDPOINTS WORK!")
    print("=" * 60)


if __name__ == "__main__":
    import uvicorn
    
    print("Starting Expanded API on http://localhost:8002")
    print("=" * 60)
    print("New endpoints:")
    print("  POST /run-test       - Run a single test")
    print("  POST /run-test-suite - Run multiple tests")
    print("  GET  /test-results   - Get test history")
    print("  GET  /metrics        - Get performance metrics")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=8002)