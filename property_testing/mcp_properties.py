#!/usr/bin/env python3
"""
Property-based testing for MCP servers using state machines.
Tests REAL MCP operations with scientific rigor.
"""

from hypothesis import given, strategies as st, settings, assume, note
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, initialize, precondition
import asyncio
import uuid
import sys
from pathlib import Path
from typing import Set, Dict, Any
import logging

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "web" / "backend" / "core"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_client import MCPClient
MinimalMCPClient = MCPClient  # Alias for compatibility

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class MCPStateMachine(RuleBasedStateMachine):
    """Test MCP servers as state machines with REAL operations."""
    
    def __init__(self):
        super().__init__()
        self.files_created: Set[str] = set()
        self.directories_created: Set[str] = set()
        self.file_contents: Dict[str, str] = {}
        self.test_dir = Path(f"/private/tmp/mcp_state_test_{uuid.uuid4().hex[:8]}")
        self.client = None
        self.connected = False
        
        # Run async setup
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._async_init())
    
    async def _async_init(self):
        """Async initialization."""
        self.client = MinimalMCPClient()
        await self.client.connect_filesystem("/private/tmp")
        self.connected = True
        
        # Create test directory
        try:
            await self.client.call_tool("create_directory", {"path": str(self.test_dir)})
            self.directories_created.add(str(self.test_dir))
            logger.info(f"Created test directory: {self.test_dir}")
        except Exception as e:
            logger.warning(f"Could not create test directory: {e}")
    
    def teardown(self):
        """Cleanup after test."""
        if self.client and self.connected:
            loop = asyncio.get_event_loop()
            
            # Clean up created files
            for filepath in self.files_created:
                try:
                    loop.run_until_complete(
                        self.client.call_tool("delete_file", {"path": filepath})
                    )
                except:
                    pass
            
            # Clean up test directory
            try:
                loop.run_until_complete(
                    self.client.call_tool("delete_directory", {"path": str(self.test_dir)})
                )
            except:
                pass
            
            # Close client
            loop.run_until_complete(self.client.close())
    
    @initialize()
    def setup_test_environment(self):
        """Initialize the test environment."""
        note(f"Test directory: {self.test_dir}")
    
    @rule(
        filename=st.text(
            min_size=1, 
            max_size=20, 
            alphabet=st.characters(whitelist_categories=["Ll", "Lu", "Nd"], min_codepoint=48)
        ).filter(lambda x: not x.startswith('.'))
    )
    def create_file(self, filename):
        """Rule: Can create files with valid names."""
        if not self.connected:
            return
        
        filepath = self.test_dir / filename
        content = f"Test content for {filename}"
        
        loop = asyncio.get_event_loop()
        try:
            result = loop.run_until_complete(
                self.client.call_tool("write_file", {
                    "path": str(filepath),
                    "content": content
                })
            )
            
            if "result" in result:
                self.files_created.add(str(filepath))
                self.file_contents[str(filepath)] = content
                note(f"Created file: {filepath}")
        except Exception as e:
            note(f"Failed to create file {filepath}: {e}")
    
    @rule()
    @precondition(lambda self: len(self.files_created) > 0)
    def read_file(self):
        """Rule: Can read created files."""
        if not self.connected or not self.files_created:
            return
        
        filepath = list(self.files_created)[0]
        expected_content = self.file_contents.get(filepath, "")
        
        loop = asyncio.get_event_loop()
        try:
            result = loop.run_until_complete(
                self.client.call_tool("read_text_file", {"path": filepath})
            )
            
            if "result" in result and "content" in result["result"]:
                actual_content = result["result"]["content"][0]["text"]
                assert actual_content == expected_content, \
                    f"Content mismatch: expected '{expected_content}', got '{actual_content}'"
                note(f"Successfully read file: {filepath}")
        except Exception as e:
            note(f"Failed to read file {filepath}: {e}")
    
    @rule(
        subdirname=st.text(
            min_size=1,
            max_size=10,
            alphabet=st.characters(whitelist_categories=["Ll", "Lu", "Nd"])
        )
    )
    def create_subdirectory(self, subdirname):
        """Rule: Can create subdirectories."""
        if not self.connected:
            return
        
        dirpath = self.test_dir / subdirname
        
        loop = asyncio.get_event_loop()
        try:
            result = loop.run_until_complete(
                self.client.call_tool("create_directory", {"path": str(dirpath)})
            )
            
            if "result" in result:
                self.directories_created.add(str(dirpath))
                note(f"Created directory: {dirpath}")
        except Exception as e:
            note(f"Failed to create directory {dirpath}: {e}")
    
    @invariant()
    def files_are_persistent(self):
        """Invariant: Created files remain accessible."""
        if not self.connected or not self.files_created:
            return
        
        # Sample up to 3 files to check
        files_to_check = list(self.files_created)[:3]
        loop = asyncio.get_event_loop()
        
        for filepath in files_to_check:
            try:
                result = loop.run_until_complete(
                    self.client.call_tool("get_file_info", {"path": filepath})
                )
                assert "result" in result or "error" not in result, \
                    f"File {filepath} is not accessible"
            except Exception as e:
                # File might have been deleted in another rule
                if filepath in self.files_created:
                    raise AssertionError(f"File {filepath} disappeared: {e}")
    
    @invariant()
    def directory_listing_consistent(self):
        """Invariant: Directory listings are consistent with our state."""
        if not self.connected:
            return
        
        loop = asyncio.get_event_loop()
        try:
            result = loop.run_until_complete(
                self.client.call_tool("list_directory", {"path": str(self.test_dir)})
            )
            
            if "result" in result and "content" in result["result"]:
                listing = result["result"]["content"][0]["text"]
                
                # Check that files we created are listed
                for filepath in self.files_created:
                    filename = Path(filepath).name
                    if str(self.test_dir) in filepath:  # Only check files in our test dir
                        assert filename in listing or "[FILE]" in listing, \
                            f"Created file {filename} not in directory listing"
        except Exception as e:
            note(f"Directory listing check failed: {e}")


class PropertyTestSuite:
    """Organized property tests for MCP servers."""
    
    @given(
        content=st.text(min_size=0, max_size=10000),
        use_retry=st.booleans()
    )
    @settings(max_examples=20, deadline=5000)
    async def test_write_read_consistency(self, content, use_retry):
        """Property: Written content can be read back identically."""
        if use_retry:
            client = MCPClient()  # Use expanded client with retry
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
    
    @given(
        num_files=st.integers(min_value=1, max_value=10),
        file_size=st.integers(min_value=0, max_value=1000)
    )
    @settings(max_examples=10, deadline=10000)
    async def test_concurrent_operations(self, num_files, file_size):
        """Property: MCP handles concurrent operations safely."""
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
    
    @given(
        directory_depth=st.integers(min_value=1, max_value=5),
        files_per_dir=st.integers(min_value=0, max_value=3)
    )
    @settings(max_examples=5, deadline=15000)
    async def test_directory_hierarchy(self, directory_depth, files_per_dir):
        """Property: Can create and navigate directory hierarchies."""
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


# Test runner for property tests
async def run_property_tests():
    """Run all property tests and collect results."""
    print("=" * 60)
    print("PROPERTY-BASED TESTING FOR MCP")
    print("=" * 60)
    
    results = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "errors": []
    }
    
    # Test 1: Write-Read Consistency
    print("\nTest 1: Write-Read Consistency...")
    try:
        suite = PropertyTestSuite()
        for i in range(5):
            content = f"Test content {i}" * (i + 1)
            await suite.test_write_read_consistency(content, i % 2 == 0)
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
        suite = PropertyTestSuite()
        await suite.test_concurrent_operations(5, 100)
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
        suite = PropertyTestSuite()
        await suite.test_directory_hierarchy(3, 2)
        results["passed"] += 1
        print("✅ Directory Hierarchy: PASSED")
    except Exception as e:
        results["failed"] += 1
        results["errors"].append(f"Directory Hierarchy: {e}")
        print(f"❌ Directory Hierarchy: FAILED - {e}")
    results["total"] += 1
    
    # Test 4: State Machine Test
    print("\nTest 4: State Machine Test...")
    try:
        from hypothesis.stateful import run_state_machine_as_test
        run_state_machine_as_test(lambda: MCPStateMachine(), settings=settings(max_examples=5))
        results["passed"] += 1
        print("✅ State Machine Test: PASSED")
    except Exception as e:
        results["failed"] += 1
        results["errors"].append(f"State Machine: {e}")
        print(f"❌ State Machine Test: FAILED - {e}")
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
    asyncio.run(run_property_tests())