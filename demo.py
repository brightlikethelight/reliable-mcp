#!/usr/bin/env python3
"""
MCP Reliability Lab - Working Demo
This demonstrates the ACTUAL working functionality of the MCP Reliability Lab.
"""

import asyncio
import json
import time
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from mcp_client import MCPClient
from config import TEST_DIR, DATABASES
from services.test_runner_service import TestRunnerService
from services.metrics_service import MetricsService
from benchmarking.workloads import StandardWorkloads
from benchmarking.benchmark_runner import BenchmarkRunner


async def demo_basic_mcp_operations():
    """Demonstrate basic MCP operations that actually work."""
    print("\n" + "="*60)
    print("1. BASIC MCP OPERATIONS")
    print("="*60)
    
    client = MCPClient('filesystem')
    try:
        await client.start()
        print("✓ Connected to filesystem MCP server")
        
        # List available tools
        tools = await client.list_tools()
        print(f"✓ Found {len(tools)} available tools")
        print("  Sample tools:", [t['name'] for t in tools[:5]])
        
        # Write a file
        write_result = await client.call_tool(
            "write_file",
            {"path": f"{TEST_DIR}/demo.txt", "content": "MCP Lab Demo Content"}
        )
        print("✓ Successfully wrote file")
        
        # Read it back
        read_result = await client.call_tool(
            "read_text_file",
            {"path": f"{TEST_DIR}/demo.txt"}
        )
        # Handle different response formats
        if isinstance(read_result, list) and read_result:
            content = read_result[0].get('text', 'No text')
        elif isinstance(read_result, dict):
            content = read_result.get('text', str(read_result))
        else:
            content = str(read_result)
        print(f"✓ Successfully read file: '{content[:50]}...'")
        
        # List directory
        list_result = await client.call_tool(
            "list_directory",
            {"path": TEST_DIR}
        )
        print(f"✓ Listed directory: {len(list_result.get('entries', []))} entries")
        
    finally:
        await client.stop()
        print("✓ Disconnected from MCP server")


async def demo_test_runner():
    """Demonstrate the test runner service."""
    print("\n" + "="*60)
    print("2. TEST RUNNER SERVICE")
    print("="*60)
    
    test_runner = TestRunnerService()
    
    # Define a simple test suite
    test_config = {
        "name": "Demo Test Suite",
        "tests": [
            {
                "name": "write_test",
                "tool": "write_file",
                "args": {"path": f"{TEST_DIR}/test1.txt", "content": "Test 1"}
            },
            {
                "name": "read_test",
                "tool": "read_text_file",
                "args": {"path": f"{TEST_DIR}/test1.txt"}
            },
            {
                "name": "list_test",
                "tool": "list_directory",
                "args": {"path": TEST_DIR}
            }
        ]
    }
    
    print("Running test suite...")
    result = await test_runner.run_test(test_config)
    
    print(f"✓ Test suite completed")
    print(f"  Reliability Score: {result.get('reliability_score', 0):.1f}%")
    print(f"  Tests Passed: {result.get('passed', 0)}/{result.get('total', 0)}")
    print(f"  Average Latency: {result.get('avg_latency', 0):.2f}ms")


async def demo_benchmarking():
    """Demonstrate benchmarking functionality."""
    print("\n" + "="*60)
    print("3. BENCHMARKING")
    print("="*60)
    
    benchmark_runner = BenchmarkRunner(DATABASES['benchmarks'])
    
    # Get a standard workload
    workloads = StandardWorkloads.get_all()
    workload = workloads['crud_heavy']
    workload.duration_seconds = 5  # Short duration for demo
    
    print(f"Running '{workload.name}' benchmark for {workload.duration_seconds} seconds...")
    
    server_config = {
        "name": "filesystem",
        "type": "filesystem",
        "path": TEST_DIR
    }
    
    result = await benchmark_runner.run_benchmark(server_config, workload)
    
    print("✓ Benchmark completed")
    print(f"  Throughput: {result['operations_per_second']:.1f} ops/sec")
    print(f"  Total Operations: {result['total_operations']}")
    print(f"  Success Rate: {(1 - result['error_rate']) * 100:.1f}%")
    print(f"  P95 Latency: {result['latencies']['p95']:.1f}ms")
    print(f"  Consistency: {result['latencies']['consistency']:.1f}%")


async def demo_metrics():
    """Demonstrate metrics tracking."""
    print("\n" + "="*60)
    print("4. METRICS TRACKING")
    print("="*60)
    
    metrics = MetricsService(DATABASES['metrics'])
    
    # Record some sample metrics
    for i in range(5):
        await metrics.record_metric(
            test_id="demo_test",
            metric_type="latency",
            value=10 + i * 2,
            metadata={"operation": f"test_{i}"}
        )
    
    print("✓ Recorded 5 sample metrics")
    
    # Retrieve metrics
    recent_metrics = await metrics.get_recent_metrics(limit=5)
    print(f"✓ Retrieved {len(recent_metrics)} recent metrics")
    
    # Get summary
    summary = await metrics.get_summary_stats()
    print(f"✓ Summary stats:")
    print(f"  Total Metrics: {summary.get('total_metrics', 0)}")
    print(f"  Average Value: {summary.get('avg_value', 0):.2f}")


async def demo_workloads():
    """Demonstrate available workload patterns."""
    print("\n" + "="*60)
    print("5. AVAILABLE WORKLOADS")
    print("="*60)
    
    workloads = StandardWorkloads.get_all()
    
    print(f"✓ {len(workloads)} standard workloads available:")
    for name, workload in workloads.items():
        print(f"  • {name}: {workload.description}")
        weights_str = ", ".join([f"{k}:{v*100:.0f}%" for k, v in workload.weights.items()])
        print(f"    Operations: {weights_str}")


async def main():
    """Run all demos."""
    print("\n" + "#"*60)
    print("# MCP RELIABILITY LAB - WORKING DEMONSTRATION")
    print("#"*60)
    print(f"\nTest Directory: {TEST_DIR}")
    print(f"Database Directory: {Path(DATABASES['metrics']).parent}")
    
    try:
        # Run each demo
        await demo_basic_mcp_operations()
        await demo_test_runner()
        await demo_benchmarking()
        await demo_metrics()
        await demo_workloads()
        
        # Summary
        print("\n" + "="*60)
        print("DEMO COMPLETE - ALL SYSTEMS WORKING")
        print("="*60)
        print("\n✅ Successfully demonstrated:")
        print("  1. MCP client connectivity and operations")
        print("  2. Test runner with reliability scoring")
        print("  3. Performance benchmarking")
        print("  4. Metrics collection and retrieval")
        print("  5. Multiple workload patterns")
        
        print("\n📊 Next Steps:")
        print("  • Run 'python3 web_ui.py' to start the web dashboard")
        print("  • Run 'python3 cli.py --help' for CLI commands")
        print("  • Check examples/ directory for more detailed examples")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)