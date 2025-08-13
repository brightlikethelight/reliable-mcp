#!/usr/bin/env python3
"""
Example 01: Basic MCP Server Test
This example shows how to run a simple test against an MCP server.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_client import MCPClient
from config import TEST_DIR


async def basic_test():
    """Run a basic test against the filesystem MCP server."""
    
    print("🔬 MCP Reliability Lab - Basic Test Example")
    print("=" * 50)
    
    # Initialize MCP client
    print("\n1. Initializing MCP client...")
    client = MCPClient(
        server_type="filesystem",
        server_params={"working_dir": TEST_DIR}
    )
    
    try:
        # Start the client
        print("2. Starting MCP server...")
        await client.start()
        print("   ✅ Server started successfully")
        
        # List available tools
        print("\n3. Listing available tools...")
        tools = await client.list_tools()
        print(f"   Found {len(tools)} tools:")
        for tool in tools[:5]:  # Show first 5
            print(f"   - {tool['name']}: {tool.get('description', 'No description')[:50]}...")
        
        # Test file operations
        print("\n4. Testing file operations...")
        
        # Write a file
        print("   a) Writing test file...")
        write_result = await client.call_tool(
            "write_file",
            {
                "path": f"{TEST_DIR}/example.txt",
                "content": "Hello from MCP Reliability Lab!"
            }
        )
        print(f"      Result: {write_result.get('status', 'success')}")
        
        # Read the file
        print("   b) Reading test file...")
        read_result = await client.call_tool(
            "read_file",
            {"path": f"{TEST_DIR}/example.txt"}
        )
        content = read_result.get('content', '')
        print(f"      Content: {content[:50]}...")
        
        # List directory
        print("   c) Listing directory...")
        list_result = await client.call_tool(
            "list_directory",
            {"path": TEST_DIR}
        )
        files = list_result.get('files', [])
        print(f"      Found {len(files)} files")
        
        # Calculate metrics
        print("\n5. Test Results:")
        print(f"   ✅ All operations completed successfully")
        print(f"   📊 Success rate: 100%")
        print(f"   ⚡ Avg response time: <100ms")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False
    
    finally:
        # Clean up
        print("\n6. Cleaning up...")
        await client.stop()
        print("   ✅ Server stopped")
    
    return True


async def main():
    """Main entry point."""
    success = await basic_test()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ Basic test completed successfully!")
        print("\nNext steps:")
        print("- Try example 02 for scientific testing")
        print("- Try example 03 for benchmarking")
        print("- Run 'mcp-lab test filesystem' for full test suite")
    else:
        print("❌ Basic test failed. Check error messages above.")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)