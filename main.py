#!/usr/bin/env python3
"""
Simple main entry point for MCP Reliability Lab.
Run tests, collect metrics, generate reports - all with real MCP operations.
"""

import asyncio
import argparse
import json
import sys
from pathlib import Path
import logging

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent))

from integration import MCPReliabilityLab

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_basic_test(lab: MCPReliabilityLab):
    """Run a basic reliability test."""
    print("\n" + "=" * 60)
    print("RUNNING BASIC RELIABILITY TEST")
    print("=" * 60)
    
    result = await lab.run_reliability_test({
        "name": "Basic Reliability Test",
        "tests": [
            {
                "name": "list_tools",
                "tool": "list_tools",
                "args": {}
            },
            {
                "name": "write_file",
                "tool": "write_file",
                "args": {
                    "path": "/private/tmp/reliability_test.txt",
                    "content": "MCP Reliability Lab Test"
                }
            },
            {
                "name": "read_file",
                "tool": "read_text_file",
                "args": {
                    "path": "/private/tmp/reliability_test.txt"
                }
            },
            {
                "name": "list_directory",
                "tool": "list_directory",
                "args": {
                    "path": "/private/tmp"
                }
            }
        ]
    })
    
    print(f"\nReliability Score: {result['score']:.1f}%")
    print(f"Tests Passed: {result['passed']}/{result['total_tests']}")
    print(f"Average Duration: {result['metrics']['avg_duration_ms']:.2f}ms")
    print(f"P95 Latency: {result['metrics']['p95_latency_ms']:.2f}ms")
    
    return result


async def run_stress_test(lab: MCPReliabilityLab, iterations: int = 10):
    """Run a stress test with multiple iterations."""
    print("\n" + "=" * 60)
    print(f"RUNNING STRESS TEST ({iterations} iterations)")
    print("=" * 60)
    
    tests = []
    for i in range(iterations):
        tests.append({
            "name": f"stress_test_{i}",
            "tool": "write_file",
            "args": {
                "path": f"/private/tmp/stress_test_{i}.txt",
                "content": f"Stress test iteration {i}"
            }
        })
    
    result = await lab.run_test_suite({
        "name": f"Stress Test Suite ({iterations} ops)",
        "tests": tests
    })
    
    print(f"\nTests Passed: {result['passed']}/{result['total_tests']}")
    print(f"Success Rate: {(result['passed']/result['total_tests']*100):.1f}%")
    print(f"Total Duration: {result['duration_ms']:.2f}ms")
    print(f"Avg per Operation: {(result['duration_ms']/result['total_tests']):.2f}ms")
    
    return result


async def generate_report(lab: MCPReliabilityLab):
    """Generate and display a reliability report."""
    print("\n" + "=" * 60)
    print("RELIABILITY REPORT")
    print("=" * 60)
    
    report = await lab.get_reliability_report()
    
    print("\nSummary:")
    print(f"  Total Tests Run: {report['summary']['total_tests_run']}")
    print(f"  Overall Success Rate: {report['summary']['overall_success_rate']*100:.1f}%")
    print(f"  Average Duration: {report['summary']['avg_duration_ms']:.2f}ms")
    
    print("\nLast 24 Hours:")
    print(f"  Operations: {report['metrics_24h']['operations']}")
    print(f"  Success Rate: {report['metrics_24h']['success_rate']*100:.1f}%")
    print(f"  P95 Latency: {report['metrics_24h']['p95_latency_ms']:.2f}ms")
    
    print("\nLast Hour:")
    print(f"  Operations: {report['metrics_1h']['operations']}")
    print(f"  Success Rate: {report['metrics_1h']['success_rate']*100:.1f}%")
    print(f"  P95 Latency: {report['metrics_1h']['p95_latency_ms']:.2f}ms")
    
    if report['per_tool']:
        print("\nTop Tools by Usage:")
        for tool in report['per_tool'][:5]:
            print(f"  {tool['tool_name']}:")
            print(f"    Operations: {tool['count']}")
            print(f"    Success Rate: {tool['success_rate']*100:.1f}%")
            print(f"    Avg Duration: {tool['avg_duration_ms']:.2f}ms")
    
    return report


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="MCP Reliability Lab - Test MCP servers with real operations"
    )
    parser.add_argument(
        "--test",
        choices=["basic", "stress", "report", "all"],
        default="basic",
        help="Type of test to run"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Number of iterations for stress test"
    )
    parser.add_argument(
        "--output",
        help="Output file for results (JSON format)"
    )
    
    args = parser.parse_args()
    
    # Initialize the lab
    print("Initializing MCP Reliability Lab...")
    lab = MCPReliabilityLab()
    
    results = {}
    
    try:
        if args.test in ["basic", "all"]:
            results["basic"] = await run_basic_test(lab)
        
        if args.test in ["stress", "all"]:
            results["stress"] = await run_stress_test(lab, args.iterations)
        
        if args.test in ["report", "all"]:
            results["report"] = await generate_report(lab)
        
        # Save results if requested
        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\nResults saved to {args.output}")
        
        print("\n" + "=" * 60)
        print("✅ MCP RELIABILITY LAB - TEST COMPLETE")
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    
    finally:
        await lab.cleanup()


if __name__ == "__main__":
    asyncio.run(main())