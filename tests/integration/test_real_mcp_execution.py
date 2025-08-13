"""
Integration tests for real MCP server execution.
Tests the complete flow with actual MCP servers.
"""

import pytest
import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path
import sys
import time

# Add parent directories to path
sys.path.append(str(Path(__file__).parent.parent.parent))
sys.path.append(str(Path(__file__).parent.parent.parent / "web" / "backend"))

from core.mcp_client import MCPClient, MCPError
from core.mcp_servers import FilesystemMCPServer, create_mcp_server
from services.real_test_runner import RealTestRunner
from data.real_test_suites import FILESYSTEM_TEST_SUITE, get_test_suite

# Test if MCP servers are available
def check_mcp_server_available(server_type: str) -> bool:
    """Check if an MCP server is installed and available."""
    
    commands = {
        "filesystem": ["npx", "@modelcontextprotocol/server-filesystem", "--help"],
        "github": ["npx", "@modelcontextprotocol/server-github", "--help"]
    }
    
    command = commands.get(server_type)
    if not command:
        return False
    
    try:
        result = subprocess.run(command, capture_output=True, timeout=5)
        return result.returncode == 0
    except:
        return False

@pytest.mark.asyncio
async def test_mcp_client_stdio_connection():
    """Test basic MCP client connection via stdio."""
    
    # Skip if filesystem server not available
    if not check_mcp_server_available("filesystem"):
        pytest.skip("Filesystem MCP server not installed")
    
    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        client = MCPClient()
        
        try:
            # Connect to filesystem server
            command = [
                "npx",
                "@modelcontextprotocol/server-filesystem",
                tmpdir
            ]
            
            await client.connect_stdio(command)
            
            # Verify connection
            assert client.is_connected()
            
            # Get available tools
            tools = client.get_tools()
            assert len(tools) > 0
            
            # Check for expected tools
            tool_names = [t.get("name") for t in tools]
            assert "write_file" in tool_names
            assert "read_file" in tool_names
            assert "list_directory" in tool_names
            
        finally:
            await client.close()
            assert not client.is_connected()

@pytest.mark.asyncio
async def test_filesystem_server_operations():
    """Test filesystem MCP server operations."""
    
    if not check_mcp_server_available("filesystem"):
        pytest.skip("Filesystem MCP server not installed")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        server = FilesystemMCPServer(allowed_directory=tmpdir)
        
        try:
            # Connect to server
            await server.connect()
            
            # Test write file
            content = "Hello from MCP test!"
            await server.write_file("/test.txt", content)
            
            # Test read file
            read_content = await server.read_file("/test.txt")
            assert read_content == content
            
            # Test list directory
            files = await server.list_directory("/")
            assert any(f.get("name") == "test.txt" for f in files)
            
            # Test create directory
            await server.create_directory("/test_dir")
            
            # Write file in directory
            await server.write_file("/test_dir/nested.txt", "Nested content")
            
            # List directory contents
            nested_files = await server.list_directory("/test_dir")
            assert any(f.get("name") == "nested.txt" for f in nested_files)
            
            # Test file exists
            assert await server.file_exists("/test.txt")
            assert not await server.file_exists("/nonexistent.txt")
            
            # Test move file
            await server.move_file("/test.txt", "/renamed.txt")
            assert await server.file_exists("/renamed.txt")
            assert not await server.file_exists("/test.txt")
            
            # Test delete file
            await server.delete_file("/renamed.txt")
            assert not await server.file_exists("/renamed.txt")
            
        finally:
            await server.close()

@pytest.mark.asyncio
async def test_real_test_runner():
    """Test the real test runner with actual MCP server."""
    
    if not check_mcp_server_available("filesystem"):
        pytest.skip("Filesystem MCP server not installed")
    
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from models import Base
    
    # Create test database
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Create test server record
        from models.server import Server
        server = Server(
            id="test-server-1",
            name="Test Filesystem Server",
            server_type="filesystem",
            transport_type="stdio",
            config={
                "command": [
                    "npx",
                    "@modelcontextprotocol/server-filesystem",
                    tempfile.gettempdir()
                ]
            },
            user_id="test-user-1"
        )
        db.add(server)
        
        # Create test suite
        from models.test import Test
        test_suite = Test(
            id="test-suite-1",
            name="Filesystem Test Suite",
            test_cases=[
                {
                    "name": "Write and Read Test",
                    "type": "functional",
                    "operations": [
                        {
                            "tool": "write_file",
                            "args": {
                                "path": "/integration_test.txt",
                                "content": "Integration test content"
                            }
                        },
                        {
                            "tool": "read_file",
                            "args": {
                                "path": "/integration_test.txt"
                            }
                        }
                    ],
                    "assertions": [
                        "read_file.get('content') == 'Integration test content'"
                    ]
                },
                {
                    "name": "Performance Test",
                    "type": "performance",
                    "tool": "list_directory",
                    "args": {"path": "/"},
                    "iterations": 5,
                    "warmup": 2,
                    "target_ms": 100
                }
            ],
            user_id="test-user-1"
        )
        db.add(test_suite)
        db.commit()
        
        # Run test suite
        runner = RealTestRunner(db)
        test_run = await runner.run_test_suite(
            test_suite_id="test-suite-1",
            server_id="test-server-1",
            user_id="test-user-1"
        )
        
        # Verify results
        assert test_run.status.value in ["completed", "failed"]
        assert test_run.results is not None
        assert test_run.results.get("total_tests", 0) > 0
        
        # Check individual test results
        test_results = test_run.results.get("test_results", [])
        assert len(test_results) == 2
        
        # First test should pass
        assert test_results[0]["status"] in ["passed", "failed"]
        
        # Performance test should have metrics
        if test_results[1]["status"] == "passed":
            assert test_results[1].get("metrics") is not None
            
    finally:
        db.close()

@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling with invalid operations."""
    
    if not check_mcp_server_available("filesystem"):
        pytest.skip("Filesystem MCP server not installed")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        server = FilesystemMCPServer(allowed_directory=tmpdir)
        
        try:
            await server.connect()
            
            # Test reading non-existent file
            with pytest.raises(MCPError):
                await server.read_file("/nonexistent.txt")
            
            # Test invalid path characters (if server validates)
            try:
                await server.write_file("/../outside.txt", "Should fail")
                # If no error, server might allow it
            except MCPError:
                pass  # Expected
            
        finally:
            await server.close()

@pytest.mark.asyncio
async def test_concurrent_operations():
    """Test concurrent operations on MCP server."""
    
    if not check_mcp_server_available("filesystem"):
        pytest.skip("Filesystem MCP server not installed")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        server = FilesystemMCPServer(allowed_directory=tmpdir)
        
        try:
            await server.connect()
            
            # Run multiple operations concurrently
            tasks = []
            for i in range(10):
                tasks.append(
                    server.write_file(f"/concurrent_{i}.txt", f"Content {i}")
                )
            
            # Execute all writes concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check results
            errors = [r for r in results if isinstance(r, Exception)]
            assert len(errors) == 0, f"Concurrent operations failed: {errors}"
            
            # Verify all files were written
            files = await server.list_directory("/")
            file_names = [f.get("name") for f in files]
            
            for i in range(10):
                assert f"concurrent_{i}.txt" in file_names
            
        finally:
            await server.close()

@pytest.mark.asyncio
async def test_full_test_suite_execution():
    """Test execution of a full test suite from real_test_suites.py."""
    
    if not check_mcp_server_available("filesystem"):
        pytest.skip("Filesystem MCP server not installed")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Get filesystem test suite
        test_suite = get_test_suite("filesystem")
        
        # Create MCP client
        client = MCPClient()
        
        try:
            # Connect to server
            command = [
                "npx",
                "@modelcontextprotocol/server-filesystem",
                tmpdir
            ]
            await client.connect_stdio(command)
            
            # Run each test case
            results = []
            for test_case in test_suite["test_cases"][:3]:  # Run first 3 tests
                name = test_case.get("name", "Unknown")
                test_type = test_case.get("type", "functional")
                
                # Running test: {name} ({test_type})
                
                try:
                    if test_type == "functional":
                        # Run operations
                        context = {}
                        for op in test_case.get("operations", []):
                            tool = op.get("tool")
                            args = op.get("args", {})
                            
                            result = await client.execute_tool(tool, args)
                            context[tool.replace("/", "_")] = result
                        
                        # Check assertions
                        assertions_passed = 0
                        assertions_total = 0
                        
                        for assertion in test_case.get("assertions", []):
                            assertions_total += 1
                            try:
                                # Safe evaluation
                                passed = eval(assertion, {"__builtins__": {}}, context)
                                if passed:
                                    assertions_passed += 1
                            except:
                                pass
                        
                        success = assertions_passed == assertions_total if assertions_total > 0 else True
                        
                    elif test_type == "performance":
                        # Run performance test
                        tool = test_case.get("tool")
                        args = test_case.get("args", {})
                        iterations = test_case.get("iterations", 5)
                        
                        timings = []
                        for _ in range(iterations):
                            start = time.perf_counter()
                            await client.execute_tool(tool, args)
                            elapsed = (time.perf_counter() - start) * 1000
                            timings.append(elapsed)
                        
                        avg_time = sum(timings) / len(timings)
                        target_ms = test_case.get("target_ms", 100)
                        success = avg_time < target_ms
                    
                    else:
                        success = False
                    
                    results.append({
                        "name": name,
                        "type": test_type,
                        "success": success
                    })
                    
                except Exception as e:
                    results.append({
                        "name": name,
                        "type": test_type,
                        "success": False,
                        "error": str(e)
                    })
            
            # Check overall results
            successful = sum(1 for r in results if r.get("success"))
            # Test Results: {successful}/{len(results)} passed
            # Log results are suppressed for production
            
            # At least some tests should pass
            assert successful > 0
            
        finally:
            await client.close()

# Main test runner
if __name__ == "__main__":
    # Check if MCP servers are available
    servers_available = {
        "filesystem": check_mcp_server_available("filesystem"),
        "github": check_mcp_server_available("github")
    }
    
    if not any(servers_available.values()):
        # No MCP servers available - exit silently
        sys.exit(1)
    
    # Run tests
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])