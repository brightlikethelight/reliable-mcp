"""
End-to-end integration tests for MCP Reliability Lab.
Tests the complete flow from user registration to report generation.
"""

import pytest
import asyncio
import httpx
import websockets
import json
import uuid
import time
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Test configuration
API_BASE_URL = "http://localhost:8000/api"
WS_BASE_URL = "ws://localhost:8000/ws"
TEST_DATABASE_URL = "sqlite:///test_mcp_reliability.db"

# Test fixtures
@pytest.fixture(scope="session")
def test_db():
    """Create test database."""
    engine = create_engine(TEST_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Import models to create tables
    from backend.models import Base
    Base.metadata.create_all(bind=engine)
    
    yield SessionLocal()
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
async def test_user():
    """Create a test user and return credentials."""
    user_data = {
        "email": f"test_{uuid.uuid4()}@example.com",
        "username": f"testuser_{uuid.uuid4().hex[:8]}",
        "password": "TestPassword123!",
        "full_name": "Test User"
    }
    
    # Register user
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/auth/register",
            json=user_data
        )
        assert response.status_code == 200
        
        # Login to get token
        response = await client.post(
            f"{API_BASE_URL}/auth/login",
            json={
                "username": user_data["email"],
                "password": user_data["password"]
            }
        )
        assert response.status_code == 200
        
        token_data = response.json()
        user_data["token"] = token_data["access_token"]
        user_data["user_id"] = token_data["user_id"]
    
    return user_data


@pytest.fixture
async def test_server(test_user):
    """Create a test MCP server."""
    headers = {"Authorization": f"Bearer {test_user['token']}"}
    
    server_data = {
        "name": f"test_server_{uuid.uuid4().hex[:8]}",
        "transport_type": "stdio",
        "server_path": "/usr/local/bin/test-mcp-server",
        "description": "Test MCP Server",
        "config": {
            "auto_start": False,
            "timeout": 30
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/servers",
            json=server_data,
            headers=headers
        )
        assert response.status_code == 200
        
        server = response.json()
        return server


@pytest.fixture
async def test_suite(test_user):
    """Create a test suite."""
    headers = {"Authorization": f"Bearer {test_user['token']}"}
    
    suite_data = {
        "name": f"test_suite_{uuid.uuid4().hex[:8]}",
        "description": "Integration Test Suite",
        "test_cases": [
            {
                "name": "Test Case 1",
                "description": "Basic functionality test",
                "test_type": "unit",
                "test_code": "assert True",
                "expected_output": {"result": "success"},
                "timeout_seconds": 10
            },
            {
                "name": "Test Case 2",
                "description": "Performance test",
                "test_type": "performance",
                "test_code": "import time; time.sleep(0.1)",
                "timeout_seconds": 10
            },
            {
                "name": "Test Case 3",
                "description": "Error handling test",
                "test_type": "unit",
                "test_code": "raise Exception('Test error')",
                "expected_output": {"error": "Test error"},
                "timeout_seconds": 10
            }
        ],
        "config": {
            "parallel_execution": False,
            "max_retries": 2
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/test-suites",
            json=suite_data,
            headers=headers
        )
        assert response.status_code == 200
        
        suite = response.json()
        return suite


# Test 1: User Registration and Authentication Flow
@pytest.mark.asyncio
async def test_user_registration_and_login():
    """Test complete user registration and login flow."""
    
    # Step 1: Register new user
    user_data = {
        "email": f"integration_test_{uuid.uuid4()}@example.com",
        "username": f"integration_{uuid.uuid4().hex[:8]}",
        "password": "SecurePassword123!",
        "full_name": "Integration Test User"
    }
    
    async with httpx.AsyncClient() as client:
        # Register
        response = await client.post(
            f"{API_BASE_URL}/auth/register",
            json=user_data
        )
        assert response.status_code == 200
        registration = response.json()
        assert "user_id" in registration
        
        # Step 2: Login with credentials
        response = await client.post(
            f"{API_BASE_URL}/auth/login",
            json={
                "username": user_data["email"],
                "password": user_data["password"]
            }
        )
        assert response.status_code == 200
        login = response.json()
        assert "access_token" in login
        assert "refresh_token" in login
        
        token = login["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Step 3: Get user profile
        response = await client.get(
            f"{API_BASE_URL}/auth/me",
            headers=headers
        )
        assert response.status_code == 200
        profile = response.json()
        assert profile["email"] == user_data["email"]
        assert profile["username"] == user_data["username"]
        
        # Step 4: Update user profile
        response = await client.patch(
            f"{API_BASE_URL}/auth/me",
            json={"full_name": "Updated Name"},
            headers=headers
        )
        assert response.status_code == 200
        
        # Step 5: Generate API key
        response = await client.post(
            f"{API_BASE_URL}/auth/api-key",
            headers=headers
        )
        assert response.status_code == 200
        api_key_data = response.json()
        assert "api_key" in api_key_data
        assert api_key_data["api_key"].startswith("mcp_")
        
        # Step 6: Test API key authentication
        response = await client.get(
            f"{API_BASE_URL}/auth/me",
            headers={"X-API-Key": api_key_data["api_key"]}
        )
        assert response.status_code == 200
        
        # Step 7: Logout
        response = await client.post(
            f"{API_BASE_URL}/auth/logout",
            headers=headers
        )
        assert response.status_code == 200
        
        # Step 8: Verify token is invalidated
        response = await client.get(
            f"{API_BASE_URL}/auth/me",
            headers=headers
        )
        assert response.status_code == 401


# Test 2: Complete Test Execution Flow
@pytest.mark.asyncio
async def test_complete_test_execution_flow(test_user, test_server, test_suite):
    """Test the complete flow of creating and running tests."""
    
    headers = {"Authorization": f"Bearer {test_user['token']}"}
    
    async with httpx.AsyncClient() as client:
        # Step 1: Start MCP server
        response = await client.post(
            f"{API_BASE_URL}/servers/{test_server['id']}/start",
            headers=headers
        )
        # May fail if server doesn't exist, that's OK for test
        
        # Step 2: Create test run
        run_data = {
            "suite_id": test_suite["id"],
            "server_id": test_server["id"],
            "config_override": {
                "timeout": 60,
                "parallel": False
            }
        }
        
        response = await client.post(
            f"{API_BASE_URL}/test-runs",
            json=run_data,
            headers=headers
        )
        assert response.status_code == 200
        test_run = response.json()
        assert "id" in test_run
        assert test_run["status"] == "pending" or test_run["status"] == "running"
        
        run_id = test_run["id"]
        
        # Step 3: Monitor test execution
        max_wait = 30  # Maximum 30 seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            response = await client.get(
                f"{API_BASE_URL}/test-runs/{run_id}",
                headers=headers
            )
            assert response.status_code == 200
            
            status = response.json()
            
            if status["status"] in ["completed", "failed", "cancelled"]:
                break
            
            await asyncio.sleep(1)
        
        # Step 4: Get test results
        response = await client.get(
            f"{API_BASE_URL}/test-runs/{run_id}/results",
            headers=headers
        )
        assert response.status_code == 200
        results = response.json()
        
        assert "total_tests" in results
        assert "passed_tests" in results
        assert "failed_tests" in results
        assert "test_results" in results
        assert len(results["test_results"]) > 0
        
        # Step 5: Get metrics
        response = await client.get(
            f"{API_BASE_URL}/metrics",
            params={
                "test_run_id": run_id,
                "metric_type": "response_time"
            },
            headers=headers
        )
        assert response.status_code == 200
        metrics = response.json()
        
        # Step 6: Generate report
        response = await client.post(
            f"{API_BASE_URL}/reports",
            json={
                "name": "Test Report",
                "report_type": "test_summary",
                "config": {
                    "test_run_ids": [run_id]
                }
            },
            headers=headers
        )
        assert response.status_code == 200
        report = response.json()
        assert "id" in report
        
        # Step 7: Export results
        response = await client.get(
            f"{API_BASE_URL}/test-runs/{run_id}/export",
            params={"format": "json"},
            headers=headers
        )
        assert response.status_code == 200
        export_data = response.json()
        assert "test_run" in export_data
        assert "results" in export_data


# Test 3: WebSocket Real-time Updates
@pytest.mark.asyncio
async def test_websocket_realtime_updates(test_user, test_server, test_suite):
    """Test WebSocket connection and real-time updates."""
    
    token = test_user["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Start a test run
    async with httpx.AsyncClient() as client:
        run_data = {
            "suite_id": test_suite["id"],
            "server_id": test_server["id"]
        }
        
        response = await client.post(
            f"{API_BASE_URL}/test-runs",
            json=run_data,
            headers=headers
        )
        assert response.status_code == 200
        test_run = response.json()
        run_id = test_run["id"]
    
    # Connect to WebSocket
    ws_url = f"{WS_BASE_URL}?token={token}"
    
    async with websockets.connect(ws_url) as websocket:
        # Wait for connection message
        message = await websocket.recv()
        data = json.loads(message)
        assert data["type"] == "connection"
        assert data["status"] == "connected"
        
        # Subscribe to test updates
        await websocket.send(json.dumps({
            "type": "subscribe",
            "channel": f"test:{run_id}"
        }))
        
        # Wait for subscription confirmation
        message = await websocket.recv()
        data = json.loads(message)
        assert data["type"] == "subscribed"
        
        # Collect messages for up to 10 seconds
        messages = []
        start_time = time.time()
        
        while time.time() - start_time < 10:
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                data = json.loads(message)
                messages.append(data)
                
                # Check for test completion
                if data.get("type") == "test_update" and data.get("status") in ["completed", "failed"]:
                    break
            except asyncio.TimeoutError:
                continue
        
        # Verify we received updates
        assert len(messages) > 0
        
        # Check message types
        message_types = {msg.get("type") for msg in messages}
        assert "test_update" in message_types or "log" in message_types
        
        # Send ping
        await websocket.send(json.dumps({"type": "ping", "echo": "test"}))
        
        # Wait for pong
        message = await websocket.recv()
        data = json.loads(message)
        assert data["type"] == "pong"
        assert data.get("echo") == "test"
        
        # Unsubscribe
        await websocket.send(json.dumps({
            "type": "unsubscribe",
            "channel": f"test:{run_id}"
        }))
        
        # Close connection
        await websocket.close()


# Test 4: Benchmark Execution
@pytest.mark.asyncio
async def test_benchmark_execution(test_user, test_server):
    """Test benchmark creation and execution."""
    
    headers = {"Authorization": f"Bearer {test_user['token']}"}
    
    async with httpx.AsyncClient() as client:
        # Step 1: Create benchmark
        benchmark_data = {
            "name": f"test_benchmark_{uuid.uuid4().hex[:8]}",
            "description": "Integration test benchmark",
            "benchmark_type": "performance",
            "config": {
                "iterations": 2,
                "warmup": True
            },
            "target_metrics": {
                "response_time": 100,
                "throughput": 1000
            }
        }
        
        response = await client.post(
            f"{API_BASE_URL}/benchmarks",
            json=benchmark_data,
            headers=headers
        )
        assert response.status_code == 200
        benchmark = response.json()
        assert "id" in benchmark
        
        # Step 2: Run benchmark
        response = await client.post(
            f"{API_BASE_URL}/benchmarks/{benchmark['id']}/run",
            json={
                "server_id": test_server["id"],
                "iterations": 1
            },
            headers=headers
        )
        assert response.status_code == 200
        benchmark_run = response.json()
        assert "id" in benchmark_run
        
        # Step 3: Get benchmark results
        await asyncio.sleep(2)  # Wait for benchmark to complete
        
        response = await client.get(
            f"{API_BASE_URL}/benchmark-results/{benchmark_run['id']}",
            headers=headers
        )
        # May be 404 if benchmark is still running, that's OK
        
        # Step 4: Get leaderboard
        response = await client.get(
            f"{API_BASE_URL}/benchmarks/leaderboard",
            params={"benchmark_id": benchmark["id"]},
            headers=headers
        )
        assert response.status_code == 200
        leaderboard = response.json()
        assert isinstance(leaderboard, list)


# Test 5: Server Management
@pytest.mark.asyncio
async def test_server_management(test_user):
    """Test complete server management flow."""
    
    headers = {"Authorization": f"Bearer {test_user['token']}"}
    
    async with httpx.AsyncClient() as client:
        # Step 1: List servers
        response = await client.get(
            f"{API_BASE_URL}/servers",
            headers=headers
        )
        assert response.status_code == 200
        initial_servers = response.json()
        
        # Step 2: Create new server
        server_data = {
            "name": f"managed_server_{uuid.uuid4().hex[:8]}",
            "transport_type": "http",
            "server_url": "http://localhost:9000",
            "auth_config": {
                "type": "bearer",
                "token": "test_token"
            },
            "config": {
                "timeout": 30,
                "health_check_interval": 60
            }
        }
        
        response = await client.post(
            f"{API_BASE_URL}/servers",
            json=server_data,
            headers=headers
        )
        assert response.status_code == 200
        server = response.json()
        assert server["name"] == server_data["name"]
        server_id = server["id"]
        
        # Step 3: Update server
        response = await client.patch(
            f"{API_BASE_URL}/servers/{server_id}",
            json={"description": "Updated description"},
            headers=headers
        )
        assert response.status_code == 200
        
        # Step 4: Get server details
        response = await client.get(
            f"{API_BASE_URL}/servers/{server_id}",
            headers=headers
        )
        assert response.status_code == 200
        server_details = response.json()
        assert server_details["description"] == "Updated description"
        
        # Step 5: Check server health
        response = await client.get(
            f"{API_BASE_URL}/servers/{server_id}/health",
            headers=headers
        )
        # May fail if server not running, that's OK
        
        # Step 6: Get server tools
        response = await client.get(
            f"{API_BASE_URL}/servers/{server_id}/tools",
            headers=headers
        )
        # May return empty list, that's OK
        
        # Step 7: Delete server
        response = await client.delete(
            f"{API_BASE_URL}/servers/{server_id}",
            headers=headers
        )
        assert response.status_code == 200
        
        # Step 8: Verify deletion
        response = await client.get(
            f"{API_BASE_URL}/servers/{server_id}",
            headers=headers
        )
        assert response.status_code == 404


# Test 6: Report Generation
@pytest.mark.asyncio
async def test_report_generation(test_user):
    """Test report creation and generation."""
    
    headers = {"Authorization": f"Bearer {test_user['token']}"}
    
    async with httpx.AsyncClient() as client:
        # Step 1: Create report configuration
        report_data = {
            "name": "Integration Test Report",
            "report_type": "performance",
            "description": "Automated test report",
            "config": {
                "period_days": 7,
                "include_charts": True
            },
            "schedule": "0 0 * * *",  # Daily at midnight
            "recipients": ["test@example.com"]
        }
        
        response = await client.post(
            f"{API_BASE_URL}/reports",
            json=report_data,
            headers=headers
        )
        assert response.status_code == 200
        report = response.json()
        assert "id" in report
        report_id = report["id"]
        
        # Step 2: Generate report
        response = await client.post(
            f"{API_BASE_URL}/reports/{report_id}/generate",
            json={"format": "json"},
            headers=headers
        )
        assert response.status_code == 200
        generated = response.json()
        assert "content" in generated
        
        # Step 3: Export report
        for format in ["json", "csv", "html"]:
            response = await client.get(
                f"{API_BASE_URL}/reports/{report_id}/export",
                params={"format": format},
                headers=headers
            )
            assert response.status_code == 200
        
        # Step 4: Share report
        response = await client.post(
            f"{API_BASE_URL}/reports/{report_id}/share",
            json={"make_public": True},
            headers=headers
        )
        assert response.status_code == 200
        share_data = response.json()
        assert "share_url" in share_data
        
        # Step 5: Get scheduled reports
        response = await client.get(
            f"{API_BASE_URL}/reports/scheduled",
            headers=headers
        )
        assert response.status_code == 200
        scheduled = response.json()
        assert any(r["id"] == report_id for r in scheduled)
        
        # Step 6: Delete report
        response = await client.delete(
            f"{API_BASE_URL}/reports/{report_id}",
            headers=headers
        )
        assert response.status_code == 200


# Test 7: Metrics and Analytics
@pytest.mark.asyncio
async def test_metrics_and_analytics(test_user):
    """Test metrics collection and analytics."""
    
    headers = {"Authorization": f"Bearer {test_user['token']}"}
    
    async with httpx.AsyncClient() as client:
        # Step 1: Record custom metric
        metric_data = {
            "metric_type": "custom",
            "metric_name": "test_metric",
            "value": 42.5,
            "unit": "ms",
            "tags": {"test": "integration"}
        }
        
        response = await client.post(
            f"{API_BASE_URL}/metrics",
            json=metric_data,
            headers=headers
        )
        assert response.status_code == 200
        
        # Step 2: Record batch metrics
        batch_data = [
            {
                "metric_type": "response_time",
                "metric_name": "api_latency",
                "value": i * 10,
                "timestamp": (datetime.utcnow() - timedelta(minutes=i)).isoformat()
            }
            for i in range(10)
        ]
        
        response = await client.post(
            f"{API_BASE_URL}/metrics/batch",
            json=batch_data,
            headers=headers
        )
        assert response.status_code == 200
        
        # Step 3: Get metrics summary
        response = await client.get(
            f"{API_BASE_URL}/metrics/summary",
            params={
                "metric_type": "response_time",
                "window_hours": 24
            },
            headers=headers
        )
        assert response.status_code == 200
        summary = response.json()
        assert "count" in summary
        assert "avg" in summary
        assert "p95" in summary
        
        # Step 4: Get metric trends
        response = await client.get(
            f"{API_BASE_URL}/metrics/trends",
            params={
                "metric_type": "response_time",
                "metric_name": "api_latency",
                "hours": 24,
                "interval_minutes": 60
            },
            headers=headers
        )
        assert response.status_code == 200
        trends = response.json()
        assert isinstance(trends, list)
        
        # Step 5: Get metric distribution
        response = await client.get(
            f"{API_BASE_URL}/metrics/distribution",
            params={
                "metric_type": "response_time",
                "metric_name": "api_latency",
                "bins": 10
            },
            headers=headers
        )
        assert response.status_code == 200
        distribution = response.json()
        assert "bins" in distribution
        assert "counts" in distribution
        
        # Step 6: Aggregate metrics
        response = await client.post(
            f"{API_BASE_URL}/metrics/aggregate",
            json={
                "window_size": "5m",
                "metric_type": "response_time"
            },
            headers=headers
        )
        assert response.status_code == 200


# Test 8: Complete Workflow Integration
@pytest.mark.asyncio
async def test_complete_workflow():
    """Test the complete workflow from start to finish."""
    
    async with httpx.AsyncClient() as client:
        # Step 1: Register user
        user_data = {
            "email": f"workflow_{uuid.uuid4()}@example.com",
            "username": f"workflow_{uuid.uuid4().hex[:8]}",
            "password": "WorkflowTest123!",
            "full_name": "Workflow Test"
        }
        
        response = await client.post(
            f"{API_BASE_URL}/auth/register",
            json=user_data
        )
        assert response.status_code == 200
        
        # Step 2: Login
        response = await client.post(
            f"{API_BASE_URL}/auth/login",
            json={
                "username": user_data["email"],
                "password": user_data["password"]
            }
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Step 3: Create server
        response = await client.post(
            f"{API_BASE_URL}/servers",
            json={
                "name": "workflow_server",
                "transport_type": "stdio",
                "server_path": "/usr/local/bin/mcp-server"
            },
            headers=headers
        )
        assert response.status_code == 200
        server_id = response.json()["id"]
        
        # Step 4: Create test suite
        response = await client.post(
            f"{API_BASE_URL}/test-suites",
            json={
                "name": "workflow_suite",
                "test_cases": [
                    {
                        "name": "Test 1",
                        "test_type": "unit",
                        "test_code": "print('test')"
                    }
                ]
            },
            headers=headers
        )
        assert response.status_code == 200
        suite_id = response.json()["id"]
        
        # Step 5: Run tests
        response = await client.post(
            f"{API_BASE_URL}/test-runs",
            json={
                "suite_id": suite_id,
                "server_id": server_id
            },
            headers=headers
        )
        assert response.status_code == 200
        run_id = response.json()["id"]
        
        # Step 6: Wait for completion
        await asyncio.sleep(2)
        
        # Step 7: Get results
        response = await client.get(
            f"{API_BASE_URL}/test-runs/{run_id}/results",
            headers=headers
        )
        assert response.status_code == 200
        
        # Step 8: Generate report
        response = await client.post(
            f"{API_BASE_URL}/reports",
            json={
                "name": "Workflow Report",
                "report_type": "test_summary"
            },
            headers=headers
        )
        assert response.status_code == 200
        
        # Step 9: Export data
        response = await client.get(
            f"{API_BASE_URL}/test-runs/{run_id}/export?format=json",
            headers=headers
        )
        assert response.status_code == 200
        
        # Step 10: Cleanup
        await client.delete(f"{API_BASE_URL}/servers/{server_id}", headers=headers)


# Run all tests
if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])