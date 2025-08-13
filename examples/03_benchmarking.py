#!/usr/bin/env python3
"""
Example 03: Performance Benchmarking
This example shows how to benchmark MCP servers with different workloads.
"""

import asyncio
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarking.benchmark_runner import BenchmarkRunner
from benchmarking.workloads import StandardWorkloads, Workload
from benchmarking.leaderboard import Leaderboard


async def run_standard_benchmark():
    """Run a standard benchmark with a predefined workload."""
    
    print("\n📊 Standard Benchmark: Real World Mix")
    print("-" * 40)
    
    runner = BenchmarkRunner()
    
    # Configure server
    server_config = {
        "name": "filesystem",
        "type": "filesystem",
        "path": "/tmp/mcp-test"
    }
    
    # Get standard workload
    workload = StandardWorkloads.get_all()["real_world_mix"]
    workload.duration_seconds = 10  # Short duration for example
    
    print(f"Workload: {workload.description}")
    print(f"Duration: {workload.duration_seconds} seconds")
    print(f"Operations: {', '.join(f'{k}:{int(v*100)}%' for k, v in workload.weights.items())}")
    print("\nRunning benchmark...")
    
    # Run benchmark
    start_time = time.time()
    results = await runner.run_benchmark(server_config, workload)
    elapsed = time.time() - start_time
    
    # Display results
    print(f"\n✅ Benchmark completed in {elapsed:.1f} seconds")
    print("\nResults:")
    print(f"  Throughput: {results['operations_per_second']:.1f} ops/sec")
    print(f"  Total operations: {results['total_operations']}")
    print(f"  Successful: {results['successful_operations']}")
    print(f"  Failed: {results['failed_operations']}")
    print(f"  Error rate: {results['error_rate']:.2%}")
    
    print("\nLatency Percentiles:")
    latencies = results['latencies']
    print(f"  P50 (median): {latencies['p50']:.1f}ms")
    print(f"  P95: {latencies['p95']:.1f}ms")
    print(f"  P99: {latencies['p99']:.1f}ms")
    print(f"  Max: {latencies['max']:.1f}ms")
    print(f"  Consistency: {latencies['consistency']:.1f}%")
    
    return results


async def run_custom_workload():
    """Create and run a custom workload."""
    
    print("\n🔧 Custom Workload: Heavy Write Operations")
    print("-" * 40)
    
    # Create custom workload
    class HeavyWriteWorkload(Workload):
        def __init__(self):
            super().__init__(
                name="heavy_writes",
                description="Custom workload with 80% writes",
                duration_seconds=10,
                weights={
                    "write_file": 0.8,    # 80% writes
                    "read_file": 0.15,    # 15% reads
                    "list_directory": 0.05 # 5% lists
                }
            )
    
    runner = BenchmarkRunner()
    server_config = {
        "name": "filesystem",
        "type": "filesystem",
        "path": "/tmp/mcp-test"
    }
    
    workload = HeavyWriteWorkload()
    
    print(f"Custom workload created:")
    print(f"  80% write operations")
    print(f"  15% read operations")
    print(f"  5% list operations")
    print("\nRunning benchmark...")
    
    results = await runner.run_benchmark(server_config, workload)
    
    print(f"\n✅ Custom benchmark completed")
    print(f"  Throughput: {results['operations_per_second']:.1f} ops/sec")
    print(f"  Write-heavy performance validated")
    
    return results


async def compare_workloads():
    """Compare performance across different workloads."""
    
    print("\n🏆 Workload Comparison")
    print("-" * 40)
    
    runner = BenchmarkRunner()
    server_config = {
        "name": "filesystem",
        "type": "filesystem",
        "path": "/tmp/mcp-test"
    }
    
    # Test different workloads
    workloads_to_test = [
        "crud_heavy",
        "read_intensive",
        "write_intensive"
    ]
    
    all_workloads = StandardWorkloads.get_all()
    results = {}
    
    print("Testing 3 different workload patterns...")
    print("(Each test runs for 5 seconds)\n")
    
    for workload_name in workloads_to_test:
        workload = all_workloads[workload_name]
        workload.duration_seconds = 5  # Short duration
        
        print(f"Testing: {workload_name}")
        result = await runner.run_benchmark(server_config, workload)
        results[workload_name] = result
        print(f"  ✅ {result['operations_per_second']:.1f} ops/sec")
    
    # Find best workload
    print("\n📊 Comparison Results:")
    best_workload = max(results.items(), key=lambda x: x[1]['operations_per_second'])
    
    print(f"Best performance: {best_workload[0]}")
    print(f"  {best_workload[1]['operations_per_second']:.1f} ops/sec")
    
    print("\nAll results (ops/sec):")
    for name, result in sorted(results.items(), key=lambda x: x[1]['operations_per_second'], reverse=True):
        print(f"  {name:20} {result['operations_per_second']:8.1f}")
    
    return results


async def update_leaderboard(results):
    """Update and display the leaderboard."""
    
    print("\n🏆 Updating Leaderboard")
    print("-" * 40)
    
    leaderboard = Leaderboard()
    
    # Add benchmark result
    score = leaderboard.add_benchmark_result(
        server="filesystem",
        workload="real_world_mix",
        result=results
    )
    
    print(f"Score calculated: {score:.1f}/100")
    
    # Get rankings
    rankings = leaderboard.get_server_rankings()
    
    if rankings:
        print("\nCurrent Rankings:")
        for i, (server, score, tests) in enumerate(rankings[:5], 1):
            print(f"  {i}. {server}: {score:.1f} (from {tests} tests)")
    else:
        print("First entry in leaderboard!")
    
    # Generate report
    html_path = leaderboard.generate_html_report("benchmark_report.html")
    print(f"\n📄 HTML report generated: {html_path}")


async def main():
    """Main entry point."""
    
    print("🔬 MCP Reliability Lab - Benchmarking Example")
    print("=" * 50)
    
    try:
        # Run different benchmark examples
        standard_results = await run_standard_benchmark()
        custom_results = await run_custom_workload()
        comparison_results = await compare_workloads()
        
        # Update leaderboard
        await update_leaderboard(standard_results)
        
        # Summary
        print("\n" + "=" * 50)
        print("✅ Benchmarking example completed!")
        print("\nWhat we demonstrated:")
        print("- Standard workload benchmarking")
        print("- Custom workload creation")
        print("- Workload comparison")
        print("- Leaderboard updates")
        print("\nNext steps:")
        print("- Try longer benchmark durations")
        print("- Test against different MCP servers")
        print("- Create your own custom workloads")
        print("- View the generated HTML report")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)