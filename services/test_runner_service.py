#!/usr/bin/env python3
"""
REAL test runner service that actually runs tests against MCP servers.
No mocks, no simulation - actual test execution.
"""

import asyncio
import sqlite3
import json
import time
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import sys
import logging

# Add path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from mcp_client import MCPClient

logger = logging.getLogger(__name__)


class TestRunnerService:
    """REAL test runner that actually runs tests."""
    
    def __init__(self, db_path: str = "mcp_test.db"):
        self.db_path = db_path
        self.mcp_client = None
        self.running_tests: Dict[str, asyncio.Task] = {}
        self._init_database()
    
    def _init_database(self):
        """Initialize test results database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS test_results (
                id TEXT PRIMARY KEY,
                test_name TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                status TEXT NOT NULL,
                duration_ms REAL,
                result TEXT,
                error_msg TEXT,
                started_at DATETIME,
                completed_at DATETIME,
                test_run_id TEXT,
                metadata TEXT
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS test_runs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                total_tests INTEGER,
                passed_tests INTEGER,
                failed_tests INTEGER,
                duration_ms REAL,
                status TEXT,
                started_at DATETIME,
                completed_at DATETIME,
                config TEXT
            )
        ''')
        conn.commit()
        conn.close()
        logger.info(f"Test database initialized at {self.db_path}")
    
    async def run_test(self, test_config: Dict[str, Any]) -> Dict:
        """Actually run a test against MCP."""
        test_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Initialize MCP client if needed
        if not self.mcp_client:
            self.mcp_client = MCPClient('filesystem')
            await self.mcp_client.start()
        
        try:
            # Extract test parameters
            tool_name = test_config.get("tool", "list_tools")
            args = test_config.get("args", {})
            test_name = test_config.get("name", f"test_{tool_name}")
            
            logger.info(f"Running test {test_id}: {test_name}")
            
            # Run real MCP operation with retry
            result = await self.mcp_client.call_tool_with_retry(
                tool_name,
                args,
                retries=test_config.get("retries", 3)
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Store real result in DB
            conn = sqlite3.connect(self.db_path)
            conn.execute('''
                INSERT INTO test_results 
                (id, test_name, tool_name, status, duration_ms, result, started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                test_id,
                test_name,
                tool_name,
                "success",
                duration_ms,
                json.dumps(result),
                datetime.fromtimestamp(start_time).isoformat(),
                datetime.now().isoformat()
            ))
            conn.commit()
            conn.close()
            
            logger.info(f"Test {test_id} completed successfully in {duration_ms:.2f}ms")
            
            return {
                "id": test_id,
                "status": "success",
                "result": result,
                "duration_ms": duration_ms,
                "test_name": test_name,
                "tool_name": tool_name
            }
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = str(e)
            
            # Store real failure
            conn = sqlite3.connect(self.db_path)
            conn.execute('''
                INSERT INTO test_results 
                (id, test_name, tool_name, status, duration_ms, error_msg, started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                test_id,
                test_config.get("name", "unknown"),
                test_config.get("tool", "unknown"),
                "failed",
                duration_ms,
                error_msg,
                datetime.fromtimestamp(start_time).isoformat(),
                datetime.now().isoformat()
            ))
            conn.commit()
            conn.close()
            
            logger.error(f"Test {test_id} failed: {error_msg}")
            
            return {
                "id": test_id,
                "status": "failed",
                "error": error_msg,
                "duration_ms": duration_ms,
                "test_name": test_config.get("name", "unknown"),
                "tool_name": test_config.get("tool", "unknown")
            }
    
    async def run_test_suite(self, suite_config: Dict[str, Any]) -> Dict:
        """Run a complete test suite."""
        suite_id = str(uuid.uuid4())
        suite_name = suite_config.get("name", "Test Suite")
        tests = suite_config.get("tests", [])
        
        logger.info(f"Starting test suite {suite_id}: {suite_name} with {len(tests)} tests")
        
        start_time = time.time()
        results = []
        passed = 0
        failed = 0
        
        # Store suite in database
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            INSERT INTO test_runs 
            (id, name, total_tests, status, started_at, config)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            suite_id,
            suite_name,
            len(tests),
            "running",
            datetime.now().isoformat(),
            json.dumps(suite_config)
        ))
        conn.commit()
        conn.close()
        
        # Run each test
        for i, test_config in enumerate(tests):
            logger.info(f"Running test {i+1}/{len(tests)}")
            
            # Add suite ID to test config
            test_config["test_run_id"] = suite_id
            
            # Run the test
            result = await self.run_test(test_config)
            results.append(result)
            
            if result["status"] == "success":
                passed += 1
            else:
                failed += 1
            
            # Check if suite was cancelled
            if suite_id in self.running_tests and self.running_tests[suite_id].cancelled():
                logger.info(f"Test suite {suite_id} cancelled")
                break
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Update suite in database
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            UPDATE test_runs 
            SET passed_tests = ?, failed_tests = ?, duration_ms = ?, 
                status = ?, completed_at = ?
            WHERE id = ?
        ''', (
            passed,
            failed,
            duration_ms,
            "completed" if failed == 0 else "completed_with_failures",
            datetime.now().isoformat(),
            suite_id
        ))
        conn.commit()
        conn.close()
        
        logger.info(f"Test suite {suite_id} completed: {passed} passed, {failed} failed")
        
        return {
            "id": suite_id,
            "name": suite_name,
            "total_tests": len(tests),
            "passed": passed,
            "failed": failed,
            "duration_ms": duration_ms,
            "results": results,
            "status": "completed" if failed == 0 else "completed_with_failures"
        }
    
    async def run_test_suite_async(self, suite_config: Dict[str, Any]) -> str:
        """Run a test suite asynchronously."""
        suite_id = str(uuid.uuid4())
        
        # Create async task
        task = asyncio.create_task(self.run_test_suite(suite_config))
        self.running_tests[suite_id] = task
        
        # Clean up when done
        def cleanup(_):
            if suite_id in self.running_tests:
                del self.running_tests[suite_id]
        
        task.add_done_callback(cleanup)
        
        return suite_id
    
    async def cancel_test_run(self, run_id: str) -> bool:
        """Cancel a running test."""
        if run_id in self.running_tests:
            self.running_tests[run_id].cancel()
            del self.running_tests[run_id]
            
            # Update database
            conn = sqlite3.connect(self.db_path)
            conn.execute('''
                UPDATE test_runs 
                SET status = ?, completed_at = ?
                WHERE id = ?
            ''', ("cancelled", datetime.now().isoformat(), run_id))
            conn.commit()
            conn.close()
            
            logger.info(f"Test run {run_id} cancelled")
            return True
        
        return False
    
    def get_test_results(self, test_id: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get test results from database."""
        conn = sqlite3.connect(self.db_path)
        
        if test_id:
            cursor = conn.execute('''
                SELECT * FROM test_results WHERE id = ?
            ''', (test_id,))
        else:
            cursor = conn.execute('''
                SELECT * FROM test_results 
                ORDER BY completed_at DESC 
                LIMIT ?
            ''', (limit,))
        
        columns = [desc[0] for desc in cursor.description]
        results = []
        
        for row in cursor.fetchall():
            result = dict(zip(columns, row))
            # Parse JSON fields
            if result.get("result"):
                try:
                    result["result"] = json.loads(result["result"])
                except:
                    pass
            results.append(result)
        
        conn.close()
        return results
    
    def get_test_runs(self, run_id: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """Get test run summaries from database."""
        conn = sqlite3.connect(self.db_path)
        
        if run_id:
            cursor = conn.execute('''
                SELECT * FROM test_runs WHERE id = ?
            ''', (run_id,))
        else:
            cursor = conn.execute('''
                SELECT * FROM test_runs 
                ORDER BY started_at DESC 
                LIMIT ?
            ''', (limit,))
        
        columns = [desc[0] for desc in cursor.description]
        runs = []
        
        for row in cursor.fetchall():
            run = dict(zip(columns, row))
            # Parse JSON config
            if run.get("config"):
                try:
                    run["config"] = json.loads(run["config"])
                except:
                    pass
            runs.append(run)
        
        conn.close()
        return runs
    
    def get_test_statistics(self) -> Dict:
        """Get overall test statistics."""
        conn = sqlite3.connect(self.db_path)
        
        # Overall stats
        cursor = conn.execute('''
            SELECT 
                COUNT(*) as total_tests,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as passed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                AVG(duration_ms) as avg_duration,
                MIN(duration_ms) as min_duration,
                MAX(duration_ms) as max_duration
            FROM test_results
        ''')
        
        overall = cursor.fetchone()
        
        # Per-tool stats
        cursor = conn.execute('''
            SELECT 
                tool_name,
                COUNT(*) as count,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as passed,
                AVG(duration_ms) as avg_duration
            FROM test_results
            GROUP BY tool_name
        ''')
        
        per_tool = []
        for row in cursor.fetchall():
            per_tool.append({
                "tool_name": row[0],
                "count": row[1],
                "passed": row[2],
                "success_rate": row[2] / row[1] if row[1] > 0 else 0,
                "avg_duration_ms": row[3]
            })
        
        conn.close()
        
        return {
            "overall": {
                "total_tests": overall[0] or 0,
                "passed": overall[1] or 0,
                "failed": overall[2] or 0,
                "success_rate": (overall[1] / overall[0]) if overall[0] else 0,
                "avg_duration_ms": overall[3] or 0,
                "min_duration_ms": overall[4] or 0,
                "max_duration_ms": overall[5] or 0
            },
            "per_tool": per_tool
        }
    
    def get_running_tests(self) -> List[str]:
        """Get list of running test IDs."""
        return list(self.running_tests.keys())
    
    async def cleanup(self):
        """Clean up resources."""
        # Cancel all running tests
        for run_id in list(self.running_tests.keys()):
            await self.cancel_test_run(run_id)
        
        # Close MCP client
        if self.mcp_client:
            await self.mcp_client.stop()
            self.mcp_client = None


# Test the service
async def test_service():
    """Test that the service actually works."""
    print("=" * 60)
    print("TESTING REAL TEST RUNNER SERVICE")
    print("=" * 60)
    
    service = TestRunnerService()
    
    # Test 1: Run single test
    print("\n1. Running single test...")
    result = await service.run_test({
        "name": "test_write_file",
        "tool": "write_file",
        "args": {
            "path": "/private/tmp/test_runner_test.txt",
            "content": "Test Runner Service Works!"
        }
    })
    
    assert result["status"] == "success", "Single test failed"
    assert result["id"] in service.get_test_results(result["id"])[0]["id"]
    print(f"✅ Single test passed in {result['duration_ms']:.2f}ms")
    
    # Test 2: Run test suite
    print("\n2. Running test suite...")
    suite_result = await service.run_test_suite({
        "name": "Basic Test Suite",
        "tests": [
            {
                "name": "list_tools",
                "tool": "list_tools",
                "args": {}
            },
            {
                "name": "create_dir",
                "tool": "create_directory",
                "args": {"path": "/private/tmp/test_dir"}
            },
            {
                "name": "write_file",
                "tool": "write_file",
                "args": {
                    "path": "/private/tmp/test_dir/test.txt",
                    "content": "Suite test"
                }
            }
        ]
    })
    
    assert suite_result["passed"] > 0, "No tests passed in suite"
    print(f"✅ Test suite completed: {suite_result['passed']}/{suite_result['total_tests']} passed")
    
    # Test 3: Get statistics
    print("\n3. Getting test statistics...")
    stats = service.get_test_statistics()
    print(f"✅ Statistics retrieved: {stats['overall']['total_tests']} total tests")
    print(f"   Success rate: {stats['overall']['success_rate']*100:.1f}%")
    
    # Test 4: Get test runs
    print("\n4. Getting test runs...")
    runs = service.get_test_runs(limit=5)
    assert len(runs) > 0, "No test runs found"
    print(f"✅ Found {len(runs)} test runs")
    
    await service.cleanup()
    
    print("\n" + "=" * 60)
    print("✅ TEST RUNNER SERVICE WORKS!")
    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_service())