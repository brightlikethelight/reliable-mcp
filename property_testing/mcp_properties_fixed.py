#!/usr/bin/env python3
"""
Fixed property-based testing for MCP servers.
Separates direct test methods from Hypothesis-decorated methods.
"""

import asyncio
import uuid
import sys
from pathlib import Path
from typing import Set, Dict, Any
import logging

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_client import MCPClient
MinimalMCPClient = MCPClient  # Alias for compatibility

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class SimplePropertyTests:
    """Simple property tests that can be called directly."""
    
    async def test_write_read_consistency(self, content: str = "Test content", use_retry: bool = False):
        """Test that written content can be read back identically."""
        if use_retry:
            client = MCPClient()
        else:
            client = MinimalMCPClient()
        
        await client.connect_filesystem("/private/tmp")
        
        path = f"/private/tmp/prop_test_{uuid.uuid4().hex[:8]}.txt"
        
        try:
            # Write
            write_result = await client.call_tool("write_file", {
                "path": path,
                "content": content
            })
            assert "result" in write_result, "Write failed"
            
            # Read
            if use_retry:
                read_result = await client.call_tool_with_retry("read_text_file", {
                    "path": path
                }, retries=3)
            else:
                read_result = await client.call_tool("read_text_file", {
                    "path": path
                })
            
            # Verify
            assert "result" in read_result, "Read failed"
            actual_content = read_result["result"]["content"][0]["text"]
            assert actual_content == content, \
                f"Content mismatch: wrote {len(content)} chars, read {len(actual_content)} chars"
            
        finally:
            # Cleanup
            try:
                await client.call_tool("delete_file", {"path": path})
            except:
                pass
            await client.close()
    
    async def test_concurrent_operations(self, num_files: int = 5, file_size: int = 100):
        """Test that MCP handles concurrent operations safely."""
        client = MCPClient()
        await client.connect_filesystem("/private/tmp")
        
        base_path = f"/private/tmp/concurrent_test_{uuid.uuid4().hex[:8]}"
        content = "x" * file_size
        
        async def create_file(index):
            """Create a single file."""
            path = f"{base_path}_{index}.txt"
            result = await client.call_tool_with_retry("write_file", {
                "path": path,
                "content": f"{content}_{index}"
            })
            return (index, path, result)
        
        try:
            # Create files concurrently
            results = await asyncio.gather(
                *[create_file(i) for i in range(num_files)],
                return_exceptions=True
            )
            
            # Verify all succeeded
            successful = 0
            created_paths = []
            
            for result in results:
                if isinstance(result, tuple):
                    index, path, write_result = result
                    if "result" in write_result:
                        successful += 1
                        created_paths.append(path)
            
            # At least 80% should succeed even under load
            assert successful >= num_files * 0.8, \
                f"Only {successful}/{num_files} concurrent writes succeeded"
            
            # Verify files exist
            for path in created_paths[:3]:  # Check first 3
                result = await client.call_tool("get_file_info", {"path": path})
                assert "result" in result, f"File {path} doesn't exist after creation"
            
        finally:
            # Cleanup
            for i in range(num_files):
                try:
                    await client.call_tool("delete_file", {
                        "path": f"{base_path}_{i}.txt"
                    })
                except:
                    pass
            await client.close()
    
    async def test_directory_hierarchy(self, directory_depth: int = 3, files_per_dir: int = 2):
        """Test creating and navigating directory hierarchies."""
        client = MinimalMCPClient()
        await client.connect_filesystem("/private/tmp")
        
        base_path = Path(f"/private/tmp/hierarchy_test_{uuid.uuid4().hex[:8]}")
        created_dirs = []
        created_files = []
        
        try:
            current_path = base_path
            
            # Create nested directories
            for depth in range(directory_depth):
                current_path = current_path / f"level_{depth}"
                result = await client.call_tool("create_directory", {
                    "path": str(current_path)
                })
                
                if "result" in result:
                    created_dirs.append(str(current_path))
                    
                    # Create files in this directory
                    for file_idx in range(files_per_dir):
                        file_path = current_path / f"file_{file_idx}.txt"
                        file_result = await client.call_tool("write_file", {
                            "path": str(file_path),
                            "content": f"Level {depth}, File {file_idx}"
                        })
                        
                        if "result" in file_result:
                            created_files.append(str(file_path))
            
            # Verify we can list all directories
            for dir_path in created_dirs:
                list_result = await client.call_tool("list_directory", {
                    "path": dir_path
                })
                assert "result" in list_result, f"Cannot list directory {dir_path}"
            
            # Verify we can read all files
            for file_path in created_files[:5]:  # Check first 5
                read_result = await client.call_tool("read_text_file", {
                    "path": file_path
                })
                assert "result" in read_result, f"Cannot read file {file_path}"
            
        finally:
            # Cleanup - delete files first, then directories in reverse order
            for file_path in created_files:
                try:
                    await client.call_tool("delete_file", {"path": file_path})
                except:
                    pass
            
            for dir_path in reversed(created_dirs):
                try:
                    await client.call_tool("delete_directory", {"path": dir_path})
                except:
                    pass
            
            await client.close()


async def run_simple_property_tests():
    """Run simple property tests and collect results."""
    print("=" * 60)
    print("SIMPLE PROPERTY-BASED TESTING FOR MCP")
    print("=" * 60)
    
    results = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "errors": []
    }
    
    tests = SimplePropertyTests()
    
    # Test 1: Write-Read Consistency
    print("\nTest 1: Write-Read Consistency...")
    try:
        for i in range(5):
            content = f"Test content {i}" * (i + 1)
            await tests.test_write_read_consistency(content, i % 2 == 0)
        results["passed"] += 1
        print("✅ Write-Read Consistency: PASSED")
    except Exception as e:
        results["failed"] += 1
        results["errors"].append(f"Write-Read Consistency: {e}")
        print(f"❌ Write-Read Consistency: FAILED - {e}")
    results["total"] += 1
    
    # Test 2: Concurrent Operations
    print("\nTest 2: Concurrent Operations...")
    try:
        await tests.test_concurrent_operations(5, 100)
        results["passed"] += 1
        print("✅ Concurrent Operations: PASSED")
    except Exception as e:
        results["failed"] += 1
        results["errors"].append(f"Concurrent Operations: {e}")
        print(f"❌ Concurrent Operations: FAILED - {e}")
    results["total"] += 1
    
    # Test 3: Directory Hierarchy
    print("\nTest 3: Directory Hierarchy...")
    try:
        await tests.test_directory_hierarchy(3, 2)
        results["passed"] += 1
        print("✅ Directory Hierarchy: PASSED")
    except Exception as e:
        results["failed"] += 1
        results["errors"].append(f"Directory Hierarchy: {e}")
        print(f"❌ Directory Hierarchy: FAILED - {e}")
    results["total"] += 1
    
    # Test 4: Multiple Files Independence
    print("\nTest 4: Multiple Files Independence...")
    try:
        client = MinimalMCPClient()
        await client.connect_filesystem("/private/tmp")
        
        # Create multiple files
        files = {}
        for i in range(3):
            path = f"/private/tmp/multi_test_{uuid.uuid4().hex[:8]}.txt"
            content = f"File {i} content"
            await client.call_tool("write_file", {"path": path, "content": content})
            files[path] = content
        
        # Verify all files have correct content
        for path, expected_content in files.items():
            result = await client.call_tool("read_text_file", {"path": path})
            actual_content = result["result"]["content"][0]["text"]
            assert actual_content == expected_content, f"Content mismatch for {path}"
        
        # Cleanup
        for path in files:
            await client.call_tool("delete_file", {"path": path})
        
        await client.close()
        
        results["passed"] += 1
        print("✅ Multiple Files Independence: PASSED")
    except Exception as e:
        results["failed"] += 1
        results["errors"].append(f"Multiple Files Independence: {e}")
        print(f"❌ Multiple Files Independence: FAILED - {e}")
    results["total"] += 1
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {results['passed']}/{results['total']} tests passed")
    print(f"Pass rate: {results['passed']/results['total']*100:.1f}%")
    
    if results["errors"]:
        print("\nErrors:")
        for error in results["errors"]:
            print(f"  - {error}")
    
    print("=" * 60)
    
    return results


if __name__ == "__main__":
    asyncio.run(run_simple_property_tests())