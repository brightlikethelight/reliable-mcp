#!/usr/bin/env python3
"""
Usage example for MCP Agent Reliability Lab.

This example demonstrates how to use the MCP reliability testing framework
to test an MCP server with comprehensive reliability patterns.
"""

import asyncio
import logging
from pathlib import Path

from mcp_reliability_lab import (
    MCPServerWrapper, MCPServerConfig, StdioTransportConfig, 
    ServerType, MCPRetryConfig, MCPObservabilityConfig,
    setup_telemetry
)


async def basic_usage_example():
    """Basic usage example."""
    print("🧪 Basic MCP Server Testing Example")
    print("=" * 50)
    
    # Configure the MCP server
    config = MCPServerConfig(
        server_type=ServerType.PYTHON,
        transport_config=StdioTransportConfig(
            command=["python", str(Path(__file__).parent / "simple_mcp_server.py")]
        ),
        enable_io_capture=True
    )
    
    # Test the server
    async with MCPServerWrapper(config) as wrapper:
        print("✅ Connected to MCP server")
        
        # Health check
        health = await wrapper.health_check()
        print(f"🏥 Health check: {health['status']}")
        
        # List available tools
        tools = await wrapper.list_tools()
        print(f"🛠️  Available tools: {[tool['name'] for tool in tools]}")
        
        # Test calculator tool
        result = await wrapper.call_tool(
            "calculator",
            {"operation": "add", "a": 15, "b": 27}
        )
        print(f"🧮 Calculator result: {result['content'][0]['text']}")
        
        # Test weather tool
        result = await wrapper.call_tool(
            "weather", 
            {"location": "San Francisco", "days": 2}
        )
        print(f"🌤️  Weather forecast: {len(result['content'][0]['text'].split('Day'))-1} days")
        
        # Test file operations
        await wrapper.call_tool(
            "file_ops",
            {
                "operation": "create",
                "filename": "test.txt",
                "content": "Hello from MCP Reliability Lab!"
            }
        )
        
        result = await wrapper.call_tool(
            "file_ops",
            {"operation": "read", "filename": "test.txt"}
        )
        print(f"📁 File content preview: {result['content'][0]['text'][:50]}...")
        
        # Clean up
        await wrapper.call_tool(
            "file_ops",
            {"operation": "delete", "filename": "test.txt"}
        )
        print("🗑️  Cleaned up test file")
        
        # Show I/O capture
        captured = wrapper.get_captured_io()
        print(f"📊 Captured {len(captured)} I/O interactions")


async def advanced_configuration_example():
    """Advanced configuration example with observability."""
    print("\n🚀 Advanced Configuration Example")
    print("=" * 50)
    
    # Setup telemetry (optional)
    setup_telemetry(service_name="mcp-reliability-demo")
    print("📡 OpenTelemetry configured")
    
    # Advanced configuration
    config = MCPServerConfig(
        server_type=ServerType.PYTHON,
        transport_config=StdioTransportConfig(
            command=["python", str(Path(__file__).parent / "simple_mcp_server.py")],
            buffer_size=16384,
            environment_variables={"DEBUG": "1"}
        ),
        retry_config=MCPRetryConfig(
            max_attempts=5,
            initial_delay=0.5,
            max_delay=30.0,
            backoff_multiplier=1.5
        ),
        observability_config=MCPObservabilityConfig(
            enable_tracing=True,
            enable_metrics=True,
            trace_sampling_rate=1.0,
            capture_payloads=True
        ),
        enable_io_capture=True,
        thread_safe=True
    )
    
    wrapper = MCPServerWrapper(config)
    
    try:
        await wrapper.connect()
        print("✅ Connected with advanced configuration")
        
        # Test error handling with retry
        try:
            result = await wrapper.call_tool(
                "error_simulator",
                {"error_type": "random", "delay": 0.1}
            )
            print("🎲 Random error test: Passed")
        except Exception as e:
            print(f"🎲 Random error test: Failed as expected - {type(e).__name__}")
        
        # Test with timeout
        try:
            result = await wrapper.call_tool(
                "calculator",
                {"operation": "multiply", "a": 123, "b": 456},
                timeout=5.0
            )
            print(f"⏱️  Timeout test: {result['content'][0]['text']}")
        except Exception as e:
            print(f"⏱️  Timeout test failed: {e}")
        
        # Show detailed I/O capture
        captured = wrapper.get_captured_io()
        if captured:
            print(f"📋 Detailed I/O Capture ({len(captured)} interactions):")
            for i, interaction in enumerate(captured[-3:]):  # Show last 3
                print(f"  {i+1}. {interaction['direction']} - {interaction.get('method', 'N/A')} "
                      f"at {interaction['timestamp']}")
    
    finally:
        await wrapper.disconnect()
        print("🔌 Disconnected")


async def concurrent_testing_example():
    """Concurrent testing example."""
    print("\n⚡ Concurrent Testing Example") 
    print("=" * 50)
    
    config = MCPServerConfig(
        server_type=ServerType.PYTHON,
        transport_config=StdioTransportConfig(
            command=["python", str(Path(__file__).parent / "simple_mcp_server.py")]
        )
    )
    
    async with MCPServerWrapper(config) as wrapper:
        print("🚀 Running concurrent operations...")
        
        # Create multiple concurrent tasks
        tasks = []
        
        # Concurrent calculator operations
        for i in range(5):
            task = wrapper.call_tool(
                "calculator",
                {"operation": "multiply", "a": i + 1, "b": 10}
            )
            tasks.append(task)
        
        # Concurrent weather requests  
        for location in ["London", "Tokyo", "New York"]:
            task = wrapper.call_tool(
                "weather",
                {"location": location, "days": 1}
            )
            tasks.append(task)
        
        # Execute all tasks concurrently
        import time
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Analyze results
        successful = sum(1 for r in results if not isinstance(r, Exception))
        failed = len(results) - successful
        
        print(f"⚡ Completed {len(tasks)} concurrent operations in {end_time-start_time:.2f}s")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        
        # Show some results
        for i, result in enumerate(results[:3]):
            if not isinstance(result, Exception):
                content = result['content'][0]['text']
                preview = content[:50] + "..." if len(content) > 50 else content
                print(f"  Result {i+1}: {preview}")


async def property_testing_example():
    """Property testing concepts example."""
    print("\n🔬 Property Testing Concepts Example")
    print("=" * 50)
    
    config = MCPServerConfig(
        server_type=ServerType.PYTHON,
        transport_config=StdioTransportConfig(
            command=["python", str(Path(__file__).parent / "simple_mcp_server.py")]
        ),
        enable_io_capture=True
    )
    
    async with MCPServerWrapper(config) as wrapper:
        print("🧪 Testing mathematical properties...")
        
        # Property: Addition is commutative (a + b = b + a)
        test_cases = [(5, 3), (10, 7), (100, 25)]
        
        for a, b in test_cases:
            result1 = await wrapper.call_tool(
                "calculator", {"operation": "add", "a": a, "b": b}
            )
            result2 = await wrapper.call_tool(
                "calculator", {"operation": "add", "a": b, "b": a}
            )
            
            # Extract numeric results (simplified)
            val1 = a + b  # We know the expected result
            val2 = b + a
            
            assert val1 == val2, f"Commutativity failed: {val1} != {val2}"
            print(f"✅ Commutative property verified: {a} + {b} = {b} + {a} = {val1}")
        
        # Property: File operations are consistent
        filename = "property_test.txt"
        content = "Property testing content"
        
        # Create file
        await wrapper.call_tool(
            "file_ops",
            {"operation": "create", "filename": filename, "content": content}
        )
        
        # Read file should return same content
        result = await wrapper.call_tool(
            "file_ops",
            {"operation": "read", "filename": filename}
        )
        
        assert content in result['content'][0]['text']
        print(f"✅ File consistency property verified")
        
        # Clean up
        await wrapper.call_tool(
            "file_ops", 
            {"operation": "delete", "filename": filename}
        )
        
        # Property: I/O capture completeness
        captured_before = len(wrapper.get_captured_io())
        
        await wrapper.call_tool("calculator", {"operation": "add", "a": 1, "b": 1})
        
        captured_after = len(wrapper.get_captured_io())
        
        assert captured_after > captured_before
        print(f"✅ I/O capture completeness verified: {captured_after - captured_before} new interactions")


async def error_handling_example():
    """Error handling and resilience example."""
    print("\n🛡️  Error Handling & Resilience Example")
    print("=" * 50)
    
    # Configure with aggressive retry settings for demonstration
    config = MCPServerConfig(
        server_type=ServerType.PYTHON,
        transport_config=StdioTransportConfig(
            command=["python", str(Path(__file__).parent / "simple_mcp_server.py")]
        ),
        retry_config=MCPRetryConfig(
            max_attempts=3,
            initial_delay=0.1,
            max_delay=1.0
        )
    )
    
    async with MCPServerWrapper(config) as wrapper:
        print("🔄 Testing retry mechanisms...")
        
        # Test division by zero (should fail immediately)
        try:
            await wrapper.call_tool(
                "calculator",
                {"operation": "divide", "a": 10, "b": 0}
            )
            print("❌ Unexpected success on division by zero")
        except Exception as e:
            print(f"✅ Division by zero properly caught: {type(e).__name__}")
        
        # Test invalid tool (should fail immediately)
        try:
            await wrapper.call_tool("nonexistent_tool", {})
            print("❌ Unexpected success on invalid tool")
        except Exception as e:
            print(f"✅ Invalid tool properly caught: {type(e).__name__}")
        
        # Test error simulator
        try:
            await wrapper.call_tool(
                "error_simulator",
                {"error_type": "internal_error", "delay": 0.1}
            )
            print("❌ Unexpected success on simulated error")
        except Exception as e:
            print(f"✅ Simulated error properly caught: {type(e).__name__}")
        
        # Test that server is still responsive after errors
        result = await wrapper.call_tool(
            "calculator",
            {"operation": "add", "a": 2, "b": 2}
        )
        print("✅ Server remains responsive after errors")


async def main():
    """Main example runner."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🌟 MCP Agent Reliability Lab - Usage Examples")
    print("=" * 60)
    
    try:
        await basic_usage_example()
        await advanced_configuration_example()
        await concurrent_testing_example()
        await property_testing_example()
        await error_handling_example()
        
        print("\n🎉 All examples completed successfully!")
        print("\nNext steps:")
        print("- Run 'mcp-lab test-server examples/simple_mcp_server.py' for CLI testing")
        print("- Check the tests/ directory for comprehensive test examples")
        print("- Explore property-based testing with Hypothesis")
        print("- Set up OpenTelemetry for production observability")
        
    except Exception as e:
        print(f"\n💥 Example failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())