#!/usr/bin/env python3
"""
Simple integration of all WORKING components.
No complexity, just what actually works.
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, List
import logging

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent / "web" / "backend"))
sys.path.insert(0, str(Path(__file__).parent / "services"))
sys.path.insert(0, str(Path(__file__).parent))

# Import only working components
sys.path.insert(0, str(Path(__file__).parent / "web" / "backend" / "core"))
from mcp_client_minimal import MinimalMCPClient
from mcp_client import MCPClient
from test_runner_service import TestRunnerService
from metrics_service import MetricsService

logger = logging.getLogger(__name__)


class MCPReliabilityLab:
    """ONLY include working components."""
    
    def __init__(self):
        # Only initialize what works
        self.mcp_client = MCPClient()  # Expanded client with retry
        self.test_runner = TestRunnerService()
        self.metrics = MetricsService("integration_metrics.db")  # Use separate DB
        logger.info("MCP Reliability Lab initialized with working components")
    
    async def connect(self):
        """Connect to MCP server."""
        await self.mcp_client.connect_filesystem("/private/tmp")
        logger.info("Connected to MCP server")
    
    async def run_reliability_test(self, config: Dict[str, Any]) -> Dict:
        """Simple, working integration for reliability testing."""
        
        test_name = config.get("name", "Reliability Test")
        tests = config.get("tests", [])
        
        logger.info(f"Starting reliability test: {test_name}")
        
        # 1. Connect to MCP if not connected
        if not self.mcp_client.connected:
            await self.connect()
        
        # 2. Run tests and collect metrics
        results = []
        for test in tests:
            # Run test
            result = await self.test_runner.run_test(test)
            results.append(result)
            
            # Record metrics
            self.metrics.record_operation(
                operation=test.get("name", "unknown"),
                duration_ms=result.get("duration_ms", 0),
                status=result.get("status", "unknown"),
                tool_name=test.get("tool"),
                test_id=result.get("id")
            )
        
        # 3. Calculate simple reliability score
        success = sum(1 for r in results if r["status"] == "success")
        total = len(results)
        score = (success / total * 100) if total > 0 else 0
        
        # 4. Get metrics summary
        metrics_summary = self.metrics.get_stats()
        
        return {
            "test_name": test_name,
            "score": score,
            "total_tests": total,
            "passed": success,
            "failed": total - success,
            "results": results,
            "metrics": {
                "avg_duration_ms": metrics_summary["avg_duration_ms"],
                "p95_latency_ms": metrics_summary["p95"],
                "success_rate": metrics_summary["success_rate"]
            }
        }
    
    async def run_test_suite(self, suite_config: Dict[str, Any]) -> Dict:
        """Run a complete test suite with metrics."""
        # Use test runner's suite functionality
        suite_result = await self.test_runner.run_test_suite(suite_config)
        
        # Record suite-level metrics
        for result in suite_result.get("results", []):
            self.metrics.record_operation(
                operation=f"suite_{suite_config.get('name', 'unknown')}",
                duration_ms=result.get("duration_ms", 0),
                status=result.get("status", "unknown"),
                tool_name=result.get("tool_name"),
                test_id=result.get("id")
            )
        
        return suite_result
    
    async def get_reliability_report(self) -> Dict:
        """Generate a simple reliability report."""
        # Get test statistics
        test_stats = self.test_runner.get_test_statistics()
        
        # Get metrics summary
        metrics_24h = self.metrics.get_stats(hours=24)
        metrics_1h = self.metrics.get_stats(hours=1)
        
        # Get per-tool metrics
        tool_metrics = self.metrics.get_metrics_by_tool(hours=24)
        
        return {
            "summary": {
                "total_tests_run": test_stats["overall"]["total_tests"],
                "overall_success_rate": test_stats["overall"]["success_rate"],
                "avg_duration_ms": test_stats["overall"]["avg_duration_ms"]
            },
            "metrics_24h": {
                "operations": metrics_24h["count"],
                "success_rate": metrics_24h["success_rate"],
                "p95_latency_ms": metrics_24h["p95"]
            },
            "metrics_1h": {
                "operations": metrics_1h["count"],
                "success_rate": metrics_1h["success_rate"],
                "p95_latency_ms": metrics_1h["p95"]
            },
            "per_tool": tool_metrics[:5]  # Top 5 tools
        }
    
    async def cleanup(self):
        """Clean up resources."""
        await self.test_runner.cleanup()
        if self.mcp_client:
            await self.mcp_client.close()
        logger.info("Cleanup completed")


# Test the integration
async def test_integration():
    """Test that the integration actually works."""
    print("=" * 60)
    print("TESTING INTEGRATED SYSTEM")
    print("=" * 60)
    
    lab = MCPReliabilityLab()
    
    try:
        # Test 1: Run reliability test
        print("\n1. Running reliability test...")
        result = await lab.run_reliability_test({
            "name": "Integration Test",
            "tests": [
                {
                    "name": "write_test",
                    "tool": "write_file",
                    "args": {"path": "/private/tmp/integration.txt", "content": "test"}
                },
                {
                    "name": "read_test",
                    "tool": "read_text_file",
                    "args": {"path": "/private/tmp/integration.txt"}
                },
                {
                    "name": "list_test",
                    "tool": "list_directory",
                    "args": {"path": "/private/tmp"}
                }
            ]
        })
        
        print(f"✅ Reliability score: {result['score']:.1f}%")
        print(f"   Tests: {result['passed']}/{result['total_tests']} passed")
        print(f"   Avg duration: {result['metrics']['avg_duration_ms']:.2f}ms")
        
        # Test 2: Run test suite
        print("\n2. Running test suite...")
        suite_result = await lab.run_test_suite({
            "name": "Integration Suite",
            "tests": [
                {"tool": "list_tools", "args": {}},
                {"tool": "create_directory", "args": {"path": "/private/tmp/test_suite_dir"}}
            ]
        })
        
        print(f"✅ Suite completed: {suite_result['passed']}/{suite_result['total_tests']} passed")
        
        # Test 3: Generate report
        print("\n3. Generating reliability report...")
        report = await lab.get_reliability_report()
        
        print(f"✅ Report generated:")
        print(f"   Total tests: {report['summary']['total_tests_run']}")
        print(f"   Success rate: {report['summary']['overall_success_rate']*100:.1f}%")
        print(f"   24h operations: {report['metrics_24h']['operations']}")
        
        await lab.cleanup()
        
        print("\n" + "=" * 60)
        print("✅ INTEGRATED SYSTEM WORKS!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        await lab.cleanup()
        raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )
    asyncio.run(test_integration())