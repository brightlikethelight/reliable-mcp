#!/usr/bin/env python3
"""
Example 04: Server Comparison
Compare multiple MCP servers side-by-side.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarking.benchmark_runner import BenchmarkRunner
from benchmarking.workloads import StandardWorkloads


async def compare_servers():
    """Compare multiple MCP servers."""
    
    print("🏆 MCP Server Comparison")
    print("=" * 50)
    
    runner = BenchmarkRunner()
    
    # Define servers to compare
    # Note: You need these servers installed for this to work
    servers = [
        {
            "name": "filesystem",
            "type": "filesystem",
            "path": "/tmp/mcp-test"
        },
        # Uncomment if you have these servers:
        # {
        #     "name": "github",
        #     "type": "github",
        #     "repo": "yourusername/test-repo"
        # },
        # {
        #     "name": "postgres",
        #     "type": "postgres",
        #     "connection": "postgresql://user:pass@localhost/testdb"
        # }
    ]
    
    if len(servers) == 1:
        print("⚠️  Only one server configured for comparison.")
        print("   Edit this file to add more servers.")
        print("   Running single server benchmark instead...\n")
    
    # Get workload
    workload = StandardWorkloads.get_all()["real_world_mix"]
    workload.duration_seconds = 10  # Short duration for example
    
    print(f"Workload: {workload.description}")
    print(f"Duration: {workload.duration_seconds} seconds per server")
    print(f"Servers to test: {', '.join(s['name'] for s in servers)}")
    print("\n" + "-" * 40)
    
    # Run comparison
    if len(servers) > 1:
        report = await runner.compare_servers(servers, workload)
        
        # Display results
        print("\n📊 Comparison Results")
        print("-" * 40)
        
        print(f"Winner: {report['winner']}")
        print(f"Winning Score: {report['summary']['winning_score']:.1f}/100")
        
        print("\nRankings:")
        for i, (server, score) in enumerate(report['rankings'], 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
            print(f"{medal} {i}. {server}: {score:.1f}")
        
        print("\nDetailed Metrics:")
        for server_name, metrics in report['details'].items():
            print(f"\n{server_name}:")
            print(f"  Throughput: {metrics['throughput']:.1f} ops/sec")
            print(f"  P95 Latency: {metrics['p95_latency']:.1f}ms")
            print(f"  Error Rate: {metrics['error_rate']:.2%}")
            print(f"  Consistency: {metrics['consistency']:.1f}%")
        
        # Save comparison report
        with open("comparison_report.json", "w") as f:
            import json
            json.dump(report, f, indent=2, default=str)
        print("\n📄 Full report saved to comparison_report.json")
        
    else:
        # Single server benchmark
        result = await runner.run_benchmark(servers[0], workload)
        print(f"\n✅ Benchmark completed for {servers[0]['name']}")
        print(f"  Throughput: {result['operations_per_second']:.1f} ops/sec")
        print(f"  P95 Latency: {result['latencies']['p95']:.1f}ms")
        print(f"  Consistency: {result['latencies']['consistency']:.1f}%")


async def head_to_head_test():
    """Run a head-to-head test with specific operations."""
    
    print("\n⚔️  Head-to-Head Test: Specific Operations")
    print("-" * 40)
    
    # This simulates what would happen with multiple servers
    operations = [
        ("Write 100 files", "write_intensive"),
        ("Read 100 files", "read_intensive"),
        ("Search operations", "search_heavy"),
        ("Concurrent access", "concurrent_stress")
    ]
    
    print("Testing specific operation types...")
    
    results = {}
    for op_name, workload_type in operations:
        print(f"\n{op_name}:")
        
        # Simulate results (in real scenario, test each server)
        # Here we just test filesystem as example
        runner = BenchmarkRunner()
        server = {
            "name": "filesystem",
            "type": "filesystem",
            "path": "/tmp/mcp-test"
        }
        
        workload = StandardWorkloads.get_all()[workload_type]
        workload.duration_seconds = 3  # Very short for example
        
        result = await runner.run_benchmark(server, workload)
        results[op_name] = result['operations_per_second']
        
        print(f"  Filesystem: {result['operations_per_second']:.1f} ops/sec")
        # In real scenario, test other servers here
    
    # Determine overall winner
    print("\n📊 Overall Performance:")
    avg_performance = sum(results.values()) / len(results)
    print(f"  Average: {avg_performance:.1f} ops/sec across all operations")


async def stress_test_comparison():
    """Compare servers under stress conditions."""
    
    print("\n🔥 Stress Test Comparison")
    print("-" * 40)
    
    print("Testing server behavior under stress...")
    
    # Create a stress workload
    class StressWorkload(StandardWorkloads.Workload):
        def __init__(self):
            super().__init__(
                name="stress_test",
                description="High-stress concurrent operations",
                duration_seconds=5,
                weights={
                    "write_file": 0.4,
                    "read_file": 0.4,
                    "list_directory": 0.2
                },
                concurrent_operations=10  # High concurrency
            )
    
    runner = BenchmarkRunner()
    server = {
        "name": "filesystem",
        "type": "filesystem",
        "path": "/tmp/mcp-test"
    }
    
    workload = StressWorkload()
    
    print(f"Concurrent operations: 10")
    print(f"Duration: {workload.duration_seconds} seconds")
    print("Running stress test...")
    
    result = await runner.run_benchmark(server, workload)
    
    print(f"\n✅ Stress test completed")
    print(f"  Throughput under stress: {result['operations_per_second']:.1f} ops/sec")
    print(f"  Error rate: {result['error_rate']:.2%}")
    print(f"  P99 Latency: {result['latencies']['p99']:.1f}ms")
    
    if result['error_rate'] < 0.01:
        print("  🟢 Server handled stress well (error rate < 1%)")
    elif result['error_rate'] < 0.05:
        print("  🟡 Server showed some strain (error rate < 5%)")
    else:
        print("  🔴 Server struggled under stress (error rate >= 5%)")


async def main():
    """Main entry point."""
    
    print("🔬 MCP Reliability Lab - Server Comparison Example")
    print("=" * 50)
    
    try:
        # Run comparison examples
        await compare_servers()
        await head_to_head_test()
        await stress_test_comparison()
        
        # Summary
        print("\n" + "=" * 50)
        print("✅ Server comparison example completed!")
        print("\nWhat we demonstrated:")
        print("- Multi-server comparison")
        print("- Head-to-head testing")
        print("- Stress test comparison")
        print("\nNext steps:")
        print("- Install additional MCP servers to compare")
        print("- Modify server configurations in the code")
        print("- Adjust workload parameters")
        print("- Use the CLI: mcp-lab compare filesystem github")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)