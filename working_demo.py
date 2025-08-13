#!/usr/bin/env python3
"""
Working Demo of MCP Reliability Lab
Shows what actually works in the current implementation
"""

import asyncio
import json
from pathlib import Path
from mcp_client import MCPClient
from config import TEST_DIR
from benchmarking.benchmark_runner import BenchmarkRunner
from benchmarking.workloads import StandardWorkloads

async def main():
    """Run a complete demo of working features."""
    
    print("=" * 60)
    print("MCP RELIABILITY LAB - WORKING DEMO")
    print("=" * 60)
    
    # 1. Basic MCP Client Test
    print("\n1. BASIC MCP CLIENT TEST")
    print("-" * 40)
    
    client = MCPClient('filesystem', {'working_dir': TEST_DIR})
    await client.start()
    
    # List tools
    tools = await client.list_tools()
    print(f"Available tools: {len(tools)}")
    for tool in tools[:3]:
        print(f"  - {tool['name']}")
    
    # Write a file
    await client.call_tool("write_file", {
        "path": f"{TEST_DIR}/demo.txt",
        "content": "MCP Reliability Lab Demo"
    })
    print(f"Created demo file at {TEST_DIR}/demo.txt")
    
    # Read the file
    result = await client.call_tool("read_file", {
        "path": f"{TEST_DIR}/demo.txt"
    })
    print(f"Read content: {result.get('content', 'N/A')[:50]}")
    
    await client.stop()
    print("Client test completed successfully")
    
    # 2. Quick Benchmark
    print("\n2. QUICK BENCHMARK TEST")
    print("-" * 40)
    
    runner = BenchmarkRunner()
    workload = StandardWorkloads.get_quick_benchmarks()["quick_mixed"]
    workload.duration_seconds = 3  # Very quick test
    
    server_config = {
        "name": "filesystem",
        "type": "filesystem",
        "path": TEST_DIR
    }
    
    results = await runner.run_benchmark(server_config, workload)
    
    # 3. Summary
    print("\n3. DEMO SUMMARY")
    print("-" * 40)
    print("Working Features:")
    print("  ✓ MCP Client - connects and communicates")
    print("  ✓ Basic Operations - read, write, list")
    print("  ✓ Benchmarking - measures performance")
    print(f"  ✓ Metrics - {results['operations_completed']} ops at {results['operations_per_second']:.1f} ops/sec")
    print(f"  ✓ Error Tracking - {results['error_rate']*100:.1f}% error rate")
    
    print("\nNot Yet Working:")
    print("  ✗ Web dashboard (partially implemented)")
    print("  ✗ Docker deployment")
    print("  ✗ Multiple server types (only filesystem)")
    print("  ✗ Real-time monitoring (SSE)")
    
    # Save results
    output_file = f"demo_results_{results['benchmark_id']}.json"
    with open(output_file, "w") as f:
        json.dump({
            "demo_timestamp": results['timestamp'],
            "operations": results['operations_completed'],
            "throughput": results['operations_per_second'],
            "error_rate": results['error_rate'],
            "latency_p95": results['latencies']['p95']
        }, f, indent=2)
    
    print(f"\nResults saved to {output_file}")
    print("=" * 60)
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)