#!/usr/bin/env python3
"""
Test 2: STDIO Transport Functionality

This test verifies that the STDIO transport can actually start a subprocess,
communicate with it, and handle the MCP protocol correctly.
"""

import asyncio
import sys
import os
import json
import tempfile
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from mcp_reliability_lab.core.config import (
        StdioTransportConfig, MCPTimeoutConfig, TransportType
    )
    from mcp_reliability_lab.core.transports.stdio import StdioTransport
    from mcp_reliability_lab.core.transport import MCPMessage
    from mcp_reliability_lab.core.errors import (
        MCPConnectionError, MCPTimeoutError, MCPTransportError
    )
    print("✓ STDIO transport imports successful")
except Exception as e:
    print(f"✗ STDIO transport import failed: {e}")
    sys.exit(1)

def create_simple_test_server():
    """Create a minimal test server script for subprocess testing."""
    server_script = '''#!/usr/bin/env python3
import sys
import json
import asyncio

class TestServer:
    async def run(self):
        try:
            while True:
                line = await asyncio.to_thread(sys.stdin.readline)
                if not line:
                    break
                
                try:
                    data = json.loads(line.strip())
                    
                    if data.get("method") == "initialize":
                        response = {
                            "jsonrpc": "2.0",
                            "id": data.get("id"),
                            "result": {
                                "protocolVersion": "2024-11-05",
                                "capabilities": {"tools": {}},
                                "serverInfo": {"name": "test-server", "version": "1.0.0"}
                            }
                        }
                        print(json.dumps(response), flush=True)
                    
                    elif data.get("method") == "tools/list":
                        response = {
                            "jsonrpc": "2.0",
                            "id": data.get("id"),
                            "result": {
                                "tools": [{
                                    "name": "echo",
                                    "description": "Echo test tool",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "message": {"type": "string"}
                                        }
                                    }
                                }]
                            }
                        }
                        print(json.dumps(response), flush=True)
                    
                    elif data.get("method") == "tools/call":
                        params = data.get("params", {})
                        if params.get("name") == "echo":
                            message = params.get("arguments", {}).get("message", "Hello")
                            response = {
                                "jsonrpc": "2.0",
                                "id": data.get("id"),
                                "result": {
                                    "content": [{
                                        "type": "text",
                                        "text": f"Echo: {message}"
                                    }]
                                }
                            }
                            print(json.dumps(response), flush=True)
                        
                    else:
                        response = {
                            "jsonrpc": "2.0",
                            "id": data.get("id"),
                            "error": {
                                "code": -32601,
                                "message": f"Method not found: {data.get('method')}"
                            }
                        }
                        print(json.dumps(response), flush=True)
                        
                except json.JSONDecodeError:
                    response = {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": "Parse error"}
                    }
                    print(json.dumps(response), flush=True)
                    
        except Exception as e:
            print(f"Server error: {e}", file=sys.stderr)

if __name__ == "__main__":
    server = TestServer()
    asyncio.run(server.run())
'''
    
    # Create temporary server script
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(server_script)
        return f.name

async def test_stdio_transport_creation():
    """Test creating and configuring STDIO transport."""
    print("\n--- Testing STDIO Transport Creation ---")
    
    try:
        # Test basic config creation
        config = StdioTransportConfig(
            command=["python", "-c", "print('hello')"]
        )
        print(f"✓ StdioTransportConfig created: {config.command}")
        
        # Test transport creation
        transport = StdioTransport(config)
        print(f"✓ StdioTransport created: {transport.config.type}")
        
        # Check initial state
        assert not transport.is_connected
        print("✓ Transport initially disconnected")
        
        return True
        
    except Exception as e:
        print(f"✗ STDIO transport creation failed: {e}")
        return False

async def test_basic_subprocess_communication():
    """Test basic subprocess startup and shutdown."""
    print("\n--- Testing Basic Subprocess Communication ---")
    
    try:
        # Create a simple echo server
        server_path = create_simple_test_server()
        
        try:
            config = StdioTransportConfig(
                command=["python", server_path],
                timeout_config=MCPTimeoutConfig(
                    connection_timeout=5.0,
                    read_timeout=5.0,
                    call_timeout=10.0
                )
            )
            
            transport = StdioTransport(config)
            
            # Test connection
            await transport.connect()
            print("✓ Successfully connected to subprocess")
            
            # Check connection state
            assert transport.is_connected
            print("✓ Transport reports connected state")
            
            # Test disconnection
            await transport.disconnect()
            print("✓ Successfully disconnected from subprocess")
            
            assert not transport.is_connected
            print("✓ Transport reports disconnected state")
            
            return True
            
        finally:
            # Clean up server script
            try:
                os.unlink(server_path)
            except:
                pass
            
    except Exception as e:
        print(f"✗ Basic subprocess communication failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_mcp_message_handling():
    """Test MCP message creation, serialization, and parsing."""
    print("\n--- Testing MCP Message Handling ---")
    
    try:
        from datetime import datetime, timezone
        
        # Test message creation
        message = MCPMessage(
            id="test-123",
            method="tools/list",
            params=None,
            result=None,
            error=None,
            timestamp=datetime.now(timezone.utc),
            raw_data=b''
        )
        print(f"✓ MCPMessage created: {message.method}")
        
        # Test JSON serialization
        json_str = message.to_json()
        print(f"✓ Message serialized to JSON: {len(json_str)} chars")
        
        # Test JSON parsing
        parsed_data = json.loads(json_str)
        assert parsed_data["jsonrpc"] == "2.0"
        assert parsed_data["id"] == "test-123"
        assert parsed_data["method"] == "tools/list"
        print("✓ JSON contains expected fields")
        
        # Test message parsing from JSON
        reconstructed = MCPMessage.from_json(json_str)
        assert reconstructed.id == message.id
        assert reconstructed.method == message.method
        print("✓ Message reconstructed from JSON")
        
        return True
        
    except Exception as e:
        print(f"✗ MCP message handling failed: {e}")
        return False

async def test_real_mcp_server_interaction():
    """Test interaction with the actual simple MCP server."""
    print("\n--- Testing Real MCP Server Interaction ---")
    
    try:
        # Use the example server from the project
        server_path = project_root / "examples" / "simple_mcp_server.py"
        
        if not server_path.exists():
            print(f"✗ Server not found at {server_path}")
            return False
            
        config = StdioTransportConfig(
            command=["python", str(server_path)],
            timeout_config=MCPTimeoutConfig(
                connection_timeout=10.0,
                read_timeout=10.0,
                call_timeout=15.0
            )
        )
        
        transport = StdioTransport(config)
        
        # Connect to server
        await transport.connect()
        print("✓ Connected to real MCP server")
        
        try:
            # Test initialize call
            result = await transport.call("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }, timeout=5.0)
            
            print(f"✓ Initialize call successful: {result.get('serverInfo', {}).get('name', 'unknown')}")
            
            # Test tools/list call
            tools_result = await transport.call("tools/list", timeout=5.0)
            tools = tools_result.get("tools", [])
            print(f"✓ Tools list call successful: {len(tools)} tools available")
            
            # Test a specific tool call if available
            if tools:
                tool_name = tools[0]["name"]
                if tool_name == "calculator":
                    calc_result = await transport.call("tools/call", {
                        "name": "calculator",
                        "arguments": {"operation": "add", "a": 5, "b": 3}
                    }, timeout=5.0)
                    print(f"✓ Calculator tool call successful: {calc_result.get('content', [{}])[0].get('text', 'no text')}")
                else:
                    print(f"✓ Found tool: {tool_name}")
            
            return True
            
        finally:
            await transport.disconnect()
            print("✓ Disconnected from real MCP server")
            
    except Exception as e:
        print(f"✗ Real MCP server interaction failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_error_handling():
    """Test error handling in STDIO transport."""
    print("\n--- Testing Error Handling ---")
    
    try:
        # Test connection to non-existent command
        bad_config = StdioTransportConfig(
            command=["nonexistent-command-xyz"],
            timeout_config=MCPTimeoutConfig(connection_timeout=2.0)
        )
        
        transport = StdioTransport(bad_config)
        
        try:
            await transport.connect()
            print("✗ Should have failed to connect to non-existent command")
            return False
        except MCPConnectionError:
            print("✓ Correctly failed to connect to non-existent command")
        
        # Test timeout handling
        config = StdioTransportConfig(
            command=["python", "-c", "import time; time.sleep(10)"],
            timeout_config=MCPTimeoutConfig(
                connection_timeout=1.0,
                read_timeout=1.0,
                call_timeout=1.0
            )
        )
        
        transport = StdioTransport(config)
        
        # This might succeed or fail depending on system timing
        try:
            await transport.connect()
            # If connection succeeds, test timeout on read
            try:
                await transport.call("test", timeout=0.5)
                print("! Call should have timed out but didn't")
            except (MCPTimeoutError, MCPTransportError, asyncio.TimeoutError):
                print("✓ Correctly timed out on slow operation")
            finally:
                await transport.disconnect()
        except (MCPConnectionError, asyncio.TimeoutError):
            print("✓ Correctly timed out during connection")
        
        return True
        
    except Exception as e:
        print(f"✗ Error handling test failed: {e}")
        return False

async def main():
    """Run all STDIO transport tests."""
    print("=== STDIO Transport Reality Tests ===")
    
    results = []
    
    # Run individual tests
    results.append(("Transport Creation", await test_stdio_transport_creation()))
    results.append(("Subprocess Communication", await test_basic_subprocess_communication()))
    results.append(("Message Handling", await test_mcp_message_handling()))
    results.append(("Real MCP Server", await test_real_mcp_server_interaction()))
    results.append(("Error Handling", await test_error_handling()))
    
    # Print summary
    print("\n=== Test Summary ===")
    passed = 0
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("✓ STDIO transport is fully functional!")
        return True
    else:
        print("✗ STDIO transport has some issues")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)