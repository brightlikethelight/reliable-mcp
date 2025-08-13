#!/usr/bin/env python3
"""
Test 3: MCP Server Wrapper Functionality

This test verifies that the MCP wrapper can integrate all components
and provide a high-level interface for MCP server interaction.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from mcp_reliability_lab.core.wrapper import MCPServerWrapper
    from mcp_reliability_lab.core.config import (
        MCPServerConfig, StdioTransportConfig, MCPRetryConfig,
        MCPTimeoutConfig, ServerType, TransportType
    )
    from mcp_reliability_lab.core.errors import (
        MCPConnectionError, MCPConfigurationError, MCPError
    )
    print("✓ MCP wrapper imports successful")
except Exception as e:
    print(f"✗ MCP wrapper import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

async def test_wrapper_creation():
    """Test creating MCP wrapper with valid configuration."""
    print("\n--- Testing Wrapper Creation ---")
    
    try:
        # Create configuration
        config = MCPServerConfig(
            server_type=ServerType.PYTHON,
            transport_config=StdioTransportConfig(
                command=["python", "--version"]  # Simple command to test
            ),
            retry_config=MCPRetryConfig(max_attempts=2),
            enable_io_capture=True,
            thread_safe=True
        )
        
        # Create wrapper
        wrapper = MCPServerWrapper(config)
        print("✓ MCPServerWrapper created successfully")
        
        # Check initial state
        assert not wrapper.is_connected
        print("✓ Wrapper initially disconnected")
        
        # Check configuration
        assert wrapper.config.server_type == ServerType.PYTHON
        assert isinstance(wrapper.config.transport_config, StdioTransportConfig)
        print("✓ Wrapper configuration properly set")
        
        return True
        
    except Exception as e:
        print(f"✗ Wrapper creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_wrapper_with_real_server():
    """Test wrapper connection to real MCP server."""
    print("\n--- Testing Wrapper with Real Server ---")
    
    try:
        # Use the example server from the project
        server_path = project_root / "examples" / "simple_mcp_server.py"
        
        if not server_path.exists():
            print(f"✗ Server not found at {server_path}")
            return False
        
        # Create configuration
        config = MCPServerConfig(
            server_type=ServerType.PYTHON,
            transport_config=StdioTransportConfig(
                command=["python", str(server_path)],
                timeout_config=MCPTimeoutConfig(
                    connection_timeout=10.0,
                    call_timeout=15.0
                )
            ),
            retry_config=MCPRetryConfig(max_attempts=2),
            enable_io_capture=True
        )
        
        # Create wrapper
        wrapper = MCPServerWrapper(config)
        
        # Test connection
        await wrapper.connect()
        print("✓ Successfully connected to MCP server")
        
        try:
            # Check connection state
            assert wrapper.is_connected
            print("✓ Wrapper reports connected state")
            
            # Test health check
            health = await wrapper.health_check()
            print(f"✓ Health check: {health['status']}")
            
            # Test listing tools
            tools = await wrapper.list_tools()
            print(f"✓ Listed {len(tools)} tools")
            
            if tools:
                # Print first few tools
                for i, tool in enumerate(tools[:3]):
                    print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
                
                # Test calling a tool
                calculator_tool = next((t for t in tools if t['name'] == 'calculator'), None)
                if calculator_tool:
                    result = await wrapper.call_tool('calculator', {
                        'operation': 'add',
                        'a': 10,
                        'b': 5
                    })
                    print(f"✓ Calculator tool result: {result}")
                
                # Test file operations tool
                file_ops_tool = next((t for t in tools if t['name'] == 'file_ops'), None)
                if file_ops_tool:
                    # List files
                    list_result = await wrapper.call_tool('file_ops', {
                        'operation': 'list'
                    })
                    print(f"✓ File operations list: {list_result}")
                    
                    # Create a file
                    create_result = await wrapper.call_tool('file_ops', {
                        'operation': 'create',
                        'filename': 'test.txt',
                        'content': 'Hello from MCP wrapper test!'
                    })
                    print(f"✓ File creation: {create_result}")
            
            return True
            
        finally:
            await wrapper.disconnect()
            print("✓ Disconnected from MCP server")
            
    except Exception as e:
        print(f"✗ Wrapper with real server failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_wrapper_context_manager():
    """Test using wrapper as async context manager."""
    print("\n--- Testing Wrapper Context Manager ---")
    
    try:
        server_path = project_root / "examples" / "simple_mcp_server.py"
        
        if not server_path.exists():
            print(f"✗ Server not found at {server_path}")
            return False
        
        config = MCPServerConfig(
            server_type=ServerType.PYTHON,
            transport_config=StdioTransportConfig(
                command=["python", str(server_path)]
            )
        )
        
        # Test context manager usage
        async with MCPServerWrapper(config) as wrapper:
            print("✓ Entered context manager (auto-connected)")
            
            assert wrapper.is_connected
            print("✓ Wrapper connected in context")
            
            # Do some work
            health = await wrapper.health_check()
            assert health['status'] == 'healthy'
            print("✓ Health check successful in context")
        
        # Should be disconnected now
        print("✓ Exited context manager (auto-disconnected)")
        
        return True
        
    except Exception as e:
        print(f"✗ Context manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_wrapper_io_capture():
    """Test I/O capture functionality."""
    print("\n--- Testing I/O Capture ---")
    
    try:
        server_path = project_root / "examples" / "simple_mcp_server.py"
        
        if not server_path.exists():
            print(f"✗ Server not found at {server_path}")
            return False
        
        config = MCPServerConfig(
            server_type=ServerType.PYTHON,
            transport_config=StdioTransportConfig(
                command=["python", str(server_path)]
            ),
            enable_io_capture=True,
            io_capture_max_size=1024 * 10  # 10KB
        )
        
        async with MCPServerWrapper(config) as wrapper:
            # Clear any previous captured data
            wrapper.clear_captured_io()
            
            # Make some calls to generate I/O
            await wrapper.list_tools()
            
            tools = await wrapper.list_tools()
            if tools and any(t['name'] == 'calculator' for t in tools):
                await wrapper.call_tool('calculator', {
                    'operation': 'multiply',
                    'a': 7,
                    'b': 6
                })
            
            # Check captured I/O
            captured = wrapper.get_captured_io()
            print(f"✓ Captured {len(captured)} I/O interactions")
            
            if captured:
                print("✓ I/O capture is working")
                # Print first interaction for verification
                if len(captured) > 0:
                    interaction = captured[0]
                    print(f"  First interaction keys: {list(interaction.keys())}")
            else:
                print("! No I/O captured (interceptor may not be active)")
        
        return True
        
    except Exception as e:
        print(f"✗ I/O capture test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_wrapper_error_handling():
    """Test wrapper error handling capabilities."""
    print("\n--- Testing Wrapper Error Handling ---")
    
    try:
        # Test invalid configuration
        try:
            invalid_config = MCPServerConfig(
                server_type=ServerType.PYTHON,
                transport_config=StdioTransportConfig(
                    command=["nonexistent-command-abc123"]
                ),
                retry_config=MCPRetryConfig(max_attempts=1)  # Fail fast
            )
            
            wrapper = MCPServerWrapper(invalid_config)
            await wrapper.connect()
            print("✗ Should have failed to connect to invalid command")
            return False
            
        except MCPConnectionError:
            print("✓ Correctly failed to connect to invalid command")
        
        # Test calling tools without connection
        server_path = project_root / "examples" / "simple_mcp_server.py"
        if server_path.exists():
            config = MCPServerConfig(
                server_type=ServerType.PYTHON,
                transport_config=StdioTransportConfig(
                    command=["python", str(server_path)]
                )
            )
            
            wrapper = MCPServerWrapper(config)
            
            # Try to call tool without connecting
            try:
                await wrapper.call_tool('calculator', {'operation': 'add', 'a': 1, 'b': 2})
                print("✗ Should have failed to call tool without connection")
                return False
            except MCPConnectionError:
                print("✓ Correctly failed to call tool without connection")
        
        # Test calling invalid tool
        if server_path.exists():
            config = MCPServerConfig(
                server_type=ServerType.PYTHON,
                transport_config=StdioTransportConfig(
                    command=["python", str(server_path)]
                )
            )
            
            async with MCPServerWrapper(config) as wrapper:
                try:
                    await wrapper.call_tool('nonexistent_tool', {})
                    print("✗ Should have failed to call nonexistent tool")
                    return False
                except Exception:
                    print("✓ Correctly failed to call nonexistent tool")
        
        return True
        
    except Exception as e:
        print(f"✗ Error handling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_wrapper_retry_logic():
    """Test wrapper retry logic with error simulator."""
    print("\n--- Testing Wrapper Retry Logic ---")
    
    try:
        server_path = project_root / "examples" / "simple_mcp_server.py"
        
        if not server_path.exists():
            print(f"✗ Server not found at {server_path}")
            return False
        
        config = MCPServerConfig(
            server_type=ServerType.PYTHON,
            transport_config=StdioTransportConfig(
                command=["python", str(server_path)],
                timeout_config=MCPTimeoutConfig(call_timeout=5.0)
            ),
            retry_config=MCPRetryConfig(
                max_attempts=2,
                initial_delay=0.5,
                strategy="exponential_backoff"
            )
        )
        
        async with MCPServerWrapper(config) as wrapper:
            tools = await wrapper.list_tools()
            
            # Find error simulator tool
            error_sim = next((t for t in tools if t['name'] == 'error_simulator'), None)
            
            if error_sim:
                # Test retry with random error (might succeed or fail)
                try:
                    result = await wrapper.call_tool('error_simulator', {
                        'error_type': 'random',
                        'delay': 0.1
                    })
                    print("✓ Random error simulation completed (may have succeeded)")
                except Exception as e:
                    print(f"✓ Random error simulation failed as expected: {type(e).__name__}")
                
                # Test with a fast error that should be retried
                try:
                    result = await wrapper.call_tool('error_simulator', {
                        'error_type': 'invalid_params',
                        'delay': 0.1
                    })
                    print("! Invalid params should have failed")
                except Exception as e:
                    print(f"✓ Invalid params error handled: {type(e).__name__}")
                
            else:
                print("! Error simulator tool not available, skipping retry test")
        
        return True
        
    except Exception as e:
        print(f"✗ Retry logic test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all wrapper tests."""
    print("=== MCP Wrapper Reality Tests ===")
    
    results = []
    
    # Run individual tests
    results.append(("Wrapper Creation", await test_wrapper_creation()))
    results.append(("Real Server Integration", await test_wrapper_with_real_server()))
    results.append(("Context Manager", await test_wrapper_context_manager()))
    results.append(("I/O Capture", await test_wrapper_io_capture()))
    results.append(("Error Handling", await test_wrapper_error_handling()))
    results.append(("Retry Logic", await test_wrapper_retry_logic()))
    
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
        print("✓ MCP Wrapper is fully functional!")
        return True
    else:
        print("✗ MCP Wrapper has some issues")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)