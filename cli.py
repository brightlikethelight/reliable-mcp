#!/usr/bin/env python3
"""
MCP Reliability Lab CLI Interface.
Provides command-line access to all testing capabilities.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import configuration
from config import TEST_DIR, DATABASES

from mcp_client import MCPClient
from scientific_test_runner_improved import ImprovedScientificTestRunner
from benchmarking.benchmark_runner import BenchmarkRunner
from benchmarking.leaderboard import Leaderboard
from benchmarking.workloads import StandardWorkloads
from services.test_runner_service import TestRunnerService


class MCPLabCLI:
    """Command-line interface for MCP Reliability Lab."""
    
    def __init__(self):
        self.test_runner = TestRunnerService()
        self.scientific_runner = ImprovedScientificTestRunner()
        self.benchmark_runner = BenchmarkRunner()
        self.leaderboard = Leaderboard()
    
    async def test_server(self, server: str, test_type: str = "basic") -> Dict[str, Any]:
        """Run a test on an MCP server."""
        
        server_config = {
            "name": server,
            "type": server,
            "path": TEST_DIR if server == "filesystem" else None
        }
        
        print(f"Testing {server} server ({test_type} mode)...")
        
        if test_type == "basic":
            # Run basic test
            test_config = {
                "name": f"CLI Test - {server}",
                "tests": [
                    {"name": "write", "tool": "write_file", "args": {"path": f"{TEST_DIR}/cli_test.txt", "content": "test"}},
                    {"name": "read", "tool": "read_text_file", "args": {"path": f"{TEST_DIR}/cli_test.txt"}},
                    {"name": "list", "tool": "list_directory", "args": {"path": TEST_DIR}}
                ]
            }
            result = await self.test_runner.run_test(test_config)
            
            print(f"Reliability Score: {result.get('reliability_score', 0):.1f}%")
            print(f"   Tests Passed: {result.get('passed', 0)}/{result.get('total', 0)}")
            
        elif test_type == "scientific":
            # Run scientific suite
            result = await self.scientific_runner.run_scientific_suite(server_config)
            score = result.get("scientific_score", {})
            
            print(f"Scientific Score: {score.get('overall_score', 0):.1f}/100")
            print(f"   Grade: {score.get('grade', 'F')}")
            print(f"   {score.get('recommendation', 'Unknown')}")
            
        else:
            print(f"ERROR: Unknown test type: {test_type}")
            return {}
        
        return result
    
    async def benchmark_server(self, server: str, workload: str = "real_world_mix", duration: int = 30) -> Dict[str, Any]:
        """Run a benchmark on an MCP server."""
        
        server_config = {
            "name": server,
            "type": server,
            "path": TEST_DIR
        }
        
        # Get workload
        workloads = StandardWorkloads.get_all()
        selected_workload = workloads.get(workload)
        
        if not selected_workload:
            print(f"ERROR: Unknown workload: {workload}")
            print(f"   Available: {', '.join(workloads.keys())}")
            return {}
        
        selected_workload.duration_seconds = duration
        
        print(f"Benchmarking {server} with {workload} for {duration}s...")
        
        result = await self.benchmark_runner.run_benchmark(server_config, selected_workload)
        
        # Add to leaderboard
        score = self.leaderboard.add_benchmark_result(server, workload, result)
        
        print(f"Benchmark Complete!")
        print(f"   Score: {score:.1f}/100")
        print(f"   Throughput: {result['operations_per_second']:.1f} ops/sec")
        print(f"   P95 Latency: {result['latencies']['p95']:.1f}ms")
        print(f"   Consistency: {result['latencies']['consistency']:.1f}%")
        
        return result
    
    async def compare_servers(self, servers: list, workload: str = "real_world_mix") -> Dict[str, Any]:
        """Compare multiple MCP servers."""
        
        print(f"Comparing servers: {', '.join(servers)}")
        
        server_configs = [
            {"name": server, "type": server, "path": TEST_DIR}
            for server in servers
        ]
        
        # Get workload
        workloads = StandardWorkloads.get_all()
        selected_workload = workloads.get(workload)
        
        if not selected_workload:
            print(f"ERROR: Unknown workload: {workload}")
            return {}
        
        # Shorten duration for comparison
        selected_workload.duration_seconds = 20
        
        report = await self.benchmark_runner.compare_servers(server_configs, selected_workload)
        
        print("\nComparison Results:")
        print(f"   Winner: {report['winner']} (Score: {report['summary']['winning_score']:.1f})")
        
        print("\n   Rankings:")
        for i, (server, score) in enumerate(report["rankings"], 1):
            print(f"   {i}. {server}: {score:.1f}")
        
        return report
    
    def show_leaderboard(self, limit: int = 10):
        """Display the leaderboard."""
        
        print("MCP Server Leaderboard")
        print("=" * 50)
        
        rankings = self.leaderboard.get_server_rankings()
        
        if rankings:
            for i, (server, score, tests) in enumerate(rankings[:limit], 1):
                medal = "#1" if i == 1 else "#2" if i == 2 else "#3" if i == 3 else "  "
                print(f"{medal} #{i}. {server:20} Score: {score:6.1f}  Tests: {tests:3}")
        else:
            print("No results yet. Run some benchmarks first!")
    
    def generate_report(self, format: str = "json", output: Optional[str] = None):
        """Generate a report."""
        
        if format == "html":
            path = self.leaderboard.generate_html_report(output or "report.html")
            print(f"HTML report generated: {path}")
        
        elif format == "json":
            data = {
                "rankings": self.leaderboard.get_server_rankings(),
                "recent": self.leaderboard.get_leaderboard(limit=20),
                "workload_bests": self.leaderboard.get_workload_bests()
            }
            
            if output:
                with open(output, "w") as f:
                    json.dump(data, f, indent=2, default=str)
                print(f"JSON report saved: {output}")
            else:
                print(json.dumps(data, indent=2, default=str))
        
        else:
            print(f"ERROR: Unknown format: {format}")


def main():
    """Main CLI entry point."""
    
    parser = argparse.ArgumentParser(
        description="MCP Reliability Lab - Scientific testing for MCP servers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mcp-lab test filesystem                    # Run basic test
  mcp-lab test filesystem --scientific       # Run scientific suite
  mcp-lab benchmark filesystem               # Run benchmark
  mcp-lab benchmark filesystem --workload crud_heavy --duration 60
  mcp-lab compare filesystem github postgres # Compare servers
  mcp-lab leaderboard                        # Show rankings
  mcp-lab report --format html --output report.html
  mcp-lab start                              # Start web UI
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Test an MCP server")
    test_parser.add_argument("server", help="Server to test (filesystem, github, etc.)")
    test_parser.add_argument("--scientific", action="store_true", help="Run scientific test suite")
    
    # Benchmark command
    bench_parser = subparsers.add_parser("benchmark", help="Benchmark an MCP server")
    bench_parser.add_argument("server", help="Server to benchmark")
    bench_parser.add_argument("--workload", default="real_world_mix", help="Workload pattern")
    bench_parser.add_argument("--duration", type=int, default=30, help="Duration in seconds")
    
    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare multiple servers")
    compare_parser.add_argument("servers", nargs="+", help="Servers to compare")
    compare_parser.add_argument("--workload", default="real_world_mix", help="Workload pattern")
    
    # Leaderboard command
    board_parser = subparsers.add_parser("leaderboard", help="Show leaderboard")
    board_parser.add_argument("--limit", type=int, default=10, help="Number of entries")
    
    # Report command
    report_parser = subparsers.add_parser("report", help="Generate report")
    report_parser.add_argument("--format", choices=["json", "html"], default="json", help="Report format")
    report_parser.add_argument("--output", help="Output file")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start web UI")
    start_parser.add_argument("--port", type=int, default=8000, help="Port number")
    start_parser.add_argument("--host", default="0.0.0.0", help="Host address")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    cli = MCPLabCLI()
    
    try:
        if args.command == "test":
            test_type = "scientific" if args.scientific else "basic"
            asyncio.run(cli.test_server(args.server, test_type))
        
        elif args.command == "benchmark":
            asyncio.run(cli.benchmark_server(args.server, args.workload, args.duration))
        
        elif args.command == "compare":
            asyncio.run(cli.compare_servers(args.servers, args.workload))
        
        elif args.command == "leaderboard":
            cli.show_leaderboard(args.limit)
        
        elif args.command == "report":
            cli.generate_report(args.format, args.output)
        
        elif args.command == "start":
            print(f"Starting MCP Reliability Lab Web UI...")
            print(f"   Open http://localhost:{args.port}")
            import uvicorn
            from web_ui import app
            uvicorn.run(app, host=args.host, port=args.port)
    
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()