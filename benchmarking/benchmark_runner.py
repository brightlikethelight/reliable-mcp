#!/usr/bin/env python3
"""
Benchmark runner for MCP servers.
Runs realistic workloads and measures performance.
"""

import asyncio
import time
import statistics
import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import sys
import logging

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))
sys.path.insert(0, str(Path(__file__).parent.parent / "web" / "backend" / "core"))

try:
    from .workloads import Workload, StandardWorkloads, WorkloadPattern
except ImportError:
    from benchmarking.workloads import Workload, StandardWorkloads, WorkloadPattern

from mcp_client import MCPClient
from services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Run benchmarks against MCP servers."""
    
    def __init__(self, db_path: str = "benchmark_results.db"):
        self.metrics = MetricsService("benchmark_metrics.db")
        self.results_db = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize benchmark results database."""
        conn = sqlite3.connect(self.results_db)
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS benchmark_runs (
                benchmark_id TEXT PRIMARY KEY,
                server_name TEXT,
                workload_name TEXT,
                pattern TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                duration_seconds REAL,
                operations_completed INTEGER,
                operations_per_second REAL,
                errors INTEGER,
                error_rate REAL,
                latencies_json TEXT,
                results_json TEXT
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS benchmark_metrics (
                metric_id TEXT PRIMARY KEY,
                benchmark_id TEXT,
                metric_name TEXT,
                metric_value REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (benchmark_id) REFERENCES benchmark_runs(benchmark_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    async def run_benchmark(
        self,
        server_config: Dict[str, Any],
        workload: Workload,
        duration_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """Run benchmark for specified duration."""
        
        # Use workload duration if not specified
        if duration_seconds is None:
            duration_seconds = workload.duration_seconds
        
        from config import TEST_DIR
        client = MCPClient('filesystem', {'working_dir': server_config.get("path", TEST_DIR)})
        await client.start()
        
        benchmark_id = f"bench_{uuid.uuid4().hex[:8]}_{int(time.time())}"
        
        print(f"\n{'=' * 60}")
        print(f"BENCHMARK: {workload.name}")
        print(f"Server: {server_config['name']}")
        print(f"Pattern: {workload.pattern.value}")
        print(f"Duration: {duration_seconds}s")
        print(f"{'=' * 60}")
        
        # Warm-up phase
        if workload.warmup_seconds > 0:
            print(f"\nWarming up for {workload.warmup_seconds}s...")
            warmup_end = time.time() + workload.warmup_seconds
            while time.time() < warmup_end:
                op = workload.select_operation()
                try:
                    params = op.generate_params()
                    await client.call_tool(op.tool, params)
                except:
                    pass
                await asyncio.sleep(0.01)
        
        # Prepare some files for read operations
        await self._prepare_test_files(client)
        
        # Main benchmark phase
        print(f"\nRunning benchmark...")
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        operations_completed = 0
        errors = 0
        latencies = []
        operation_latencies = {}  # Track per-operation latencies
        
        # Progress tracking
        last_progress = 0
        
        while time.time() < end_time:
            # Select operation
            op = workload.select_operation()
            
            # Track per-operation metrics
            if op.tool not in operation_latencies:
                operation_latencies[op.tool] = []
            
            op_start = time.time()
            
            try:
                # Generate parameters
                params = op.generate_params()
                
                # Execute operation
                if workload.pattern == WorkloadPattern.PARALLEL and operations_completed % 5 == 0:
                    # Run 5 operations in parallel every 5th operation
                    tasks = []
                    for _ in range(5):
                        next_op = workload.select_operation()
                        next_params = next_op.generate_params()
                        tasks.append(client.call_tool_with_retry(next_op.tool, next_params, retries=1))
                    
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    for result in results:
                        if isinstance(result, Exception):
                            errors += 1
                        elif result is not None and result != {}:
                            operations_completed += 1
                        else:
                            errors += 1
                    
                    latency = (time.time() - op_start) * 1000 / len(tasks)
                    for _ in range(len(tasks)):
                        latencies.append(latency)
                else:
                    # Sequential operation
                    result = await client.call_tool_with_retry(op.tool, params, retries=1)
                    
                    # Check if operation succeeded (result is not empty/None)
                    if result is not None and result != {}:
                        operations_completed += 1
                    else:
                        errors += 1
                    
                    latency = (time.time() - op_start) * 1000
                    latencies.append(latency)
                    operation_latencies[op.tool].append(latency)
                
                # Record in metrics service
                self.metrics.record_operation(
                    operation=op.tool,
                    duration_ms=latency,
                    status="success" if (result is not None and result != {}) else "error",
                    tool_name=op.tool
                )
                
            except Exception as e:
                errors += 1
                logger.debug(f"Operation error: {e}")
                self.metrics.record_operation(
                    operation=op.tool,
                    duration_ms=0,
                    status="error",
                    tool_name=op.tool,
                    error_msg=str(e)[:100]
                )
            
            # Control rate based on pattern
            if workload.pattern == WorkloadPattern.SEQUENTIAL:
                await asyncio.sleep(0.005)  # Small delay between ops
            elif workload.pattern == WorkloadPattern.BURST:
                if operations_completed % 10 == 0:
                    await asyncio.sleep(0.5)  # Pause between bursts
            
            # Progress indicator
            progress = int((time.time() - start_time) / duration_seconds * 100)
            if progress > last_progress + 10:
                print(f"  Progress: {progress}%")
                last_progress = progress
        
        # Calculate results
        actual_duration = time.time() - start_time
        
        # Calculate latency statistics
        if latencies:
            sorted_latencies = sorted(latencies)
            
            # Filter outliers for consistency calculation
            trim_count = max(1, len(sorted_latencies) // 10)
            trimmed = sorted_latencies[trim_count:-trim_count] if len(sorted_latencies) > 2 * trim_count else sorted_latencies
            
            # Calculate consistency
            if len(trimmed) > 1:
                mean = statistics.mean(trimmed)
                stdev = statistics.stdev(trimmed)
                cv = (stdev / mean) * 100 if mean > 0 else 0
                consistency = max(0, 100 - min(cv, 100))
            else:
                consistency = 100
            
            latency_stats = {
                "min": min(sorted_latencies),
                "max": max(sorted_latencies),
                "avg": statistics.mean(sorted_latencies),
                "median": statistics.median(sorted_latencies),
                "p50": sorted_latencies[len(sorted_latencies) // 2],
                "p95": sorted_latencies[int(len(sorted_latencies) * 0.95)],
                "p99": sorted_latencies[int(len(sorted_latencies) * 0.99)] if len(sorted_latencies) > 100 else sorted_latencies[-1],
                "stdev": statistics.stdev(sorted_latencies) if len(sorted_latencies) > 1 else 0,
                "consistency": consistency
            }
        else:
            latency_stats = {
                "min": 0, "max": 0, "avg": 0, "median": 0,
                "p50": 0, "p95": 0, "p99": 0, "stdev": 0,
                "consistency": 0
            }
        
        # Per-operation statistics
        op_stats = {}
        for tool, tool_latencies in operation_latencies.items():
            if tool_latencies:
                op_stats[tool] = {
                    "count": len(tool_latencies),
                    "avg_ms": statistics.mean(tool_latencies),
                    "min_ms": min(tool_latencies),
                    "max_ms": max(tool_latencies)
                }
        
        results = {
            "benchmark_id": benchmark_id,
            "server": server_config["name"],
            "workload": workload.name,
            "pattern": workload.pattern.value,
            "duration": actual_duration,
            "operations_completed": operations_completed,
            "operations_per_second": operations_completed / actual_duration if actual_duration > 0 else 0,
            "errors": errors,
            "error_rate": errors / (operations_completed + errors) if (operations_completed + errors) > 0 else 0,
            "latencies": latency_stats,
            "per_operation": op_stats,
            "timestamp": datetime.now().isoformat()
        }
        
        # Store results
        self.store_benchmark_results(results)
        
        # Cleanup
        await client.stop()
        
        # Print summary
        print(f"\n{'=' * 60}")
        print(f"BENCHMARK RESULTS")
        print(f"{'=' * 60}")
        print(f"Operations: {operations_completed} ({results['operations_per_second']:.1f} ops/sec)")
        print(f"Errors: {errors} ({results['error_rate']*100:.1f}%)")
        print(f"Latency - Avg: {latency_stats['avg']:.1f}ms, P95: {latency_stats['p95']:.1f}ms")
        print(f"Consistency: {latency_stats['consistency']:.1f}/100")
        print(f"{'=' * 60}")
        
        return results
    
    async def _prepare_test_files(self, client):
        """Prepare test files for read operations."""
        from config import TEST_DIR
        test_files = [
            (f"{TEST_DIR}/bench_read.txt", "Test content for reading"),
            (f"{TEST_DIR}/bench_delete_test.txt", "File to be deleted"),
        ]
        
        for path, content in test_files:
            try:
                await client.call_tool("write_file", {"path": path, "content": content})
            except:
                pass
    
    def store_benchmark_results(self, results: Dict[str, Any]):
        """Store benchmark results in database."""
        conn = sqlite3.connect(self.results_db)
        
        conn.execute('''
            INSERT INTO benchmark_runs 
            (benchmark_id, server_name, workload_name, pattern, duration_seconds,
             operations_completed, operations_per_second, errors, error_rate,
             latencies_json, results_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            results["benchmark_id"],
            results["server"],
            results["workload"],
            results["pattern"],
            results["duration"],
            results["operations_completed"],
            results["operations_per_second"],
            results["errors"],
            results["error_rate"],
            json.dumps(results["latencies"]),
            json.dumps(results)
        ))
        
        # Store individual metrics
        metrics = [
            ("throughput", results["operations_per_second"]),
            ("error_rate", results["error_rate"]),
            ("avg_latency", results["latencies"]["avg"]),
            ("p95_latency", results["latencies"]["p95"]),
            ("p99_latency", results["latencies"]["p99"]),
            ("consistency", results["latencies"]["consistency"])
        ]
        
        for metric_name, metric_value in metrics:
            metric_id = f"{results['benchmark_id']}_{metric_name}"
            conn.execute('''
                INSERT INTO benchmark_metrics (metric_id, benchmark_id, metric_name, metric_value)
                VALUES (?, ?, ?, ?)
            ''', (metric_id, results["benchmark_id"], metric_name, metric_value))
        
        conn.commit()
        conn.close()
    
    async def compare_servers(
        self,
        server_configs: List[Dict[str, Any]],
        workload: Workload
    ) -> Dict[str, Any]:
        """Compare multiple MCP servers with the same workload."""
        
        print(f"\n{'=' * 60}")
        print(f"SERVER COMPARISON: {workload.name}")
        print(f"{'=' * 60}")
        
        comparison_results = {
            "workload": workload.name,
            "timestamp": datetime.now().isoformat(),
            "servers": {}
        }
        
        for config in server_configs:
            print(f"\nBenchmarking {config['name']}...")
            results = await self.run_benchmark(config, workload)
            comparison_results["servers"][config["name"]] = results
        
        # Generate comparison report
        report = self.generate_comparison_report(comparison_results)
        
        return report
    
    def generate_comparison_report(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate detailed comparison report."""
        
        report = {
            "workload": results["workload"],
            "timestamp": results["timestamp"],
            "winner": None,
            "rankings": [],
            "detailed_comparison": {},
            "summary": {}
        }
        
        # Calculate scores for each server
        scores = {}
        for server, data in results["servers"].items():
            # Scoring formula (higher is better)
            throughput_score = data["operations_per_second"] / 10  # Normalize to 0-100
            error_penalty = data["error_rate"] * 50  # Penalty for errors
            latency_penalty = min(data["latencies"]["p95"] / 10, 50)  # Cap at 50
            consistency_bonus = data["latencies"]["consistency"] / 2  # Bonus for consistency
            
            score = max(0, 100 + throughput_score - error_penalty - latency_penalty + consistency_bonus)
            scores[server] = score
        
        # Rank servers
        report["rankings"] = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        report["winner"] = report["rankings"][0][0] if report["rankings"] else None
        
        # Detailed comparison
        metrics_to_compare = [
            ("operations_per_second", "higher_better"),
            ("error_rate", "lower_better"),
            ("avg_latency", "lower_better"),
            ("p95_latency", "lower_better"),
            ("consistency", "higher_better")
        ]
        
        for metric, better_direction in metrics_to_compare:
            report["detailed_comparison"][metric] = {}
            values = []
            
            for server, data in results["servers"].items():
                if metric in ["avg_latency", "p95_latency", "consistency"]:
                    value = data["latencies"].get(metric.replace("_latency", ""), 0)
                else:
                    value = data.get(metric, 0)
                
                report["detailed_comparison"][metric][server] = value
                values.append((server, value))
            
            # Mark best performer
            if better_direction == "higher_better":
                best = max(values, key=lambda x: x[1])
            else:
                best = min(values, key=lambda x: x[1])
            
            report["detailed_comparison"][metric]["best"] = best[0]
        
        # Summary
        if report["winner"]:
            winner_data = results["servers"][report["winner"]]
            report["summary"] = {
                "winner": report["winner"],
                "winning_score": scores[report["winner"]],
                "winner_throughput": winner_data["operations_per_second"],
                "winner_p95_latency": winner_data["latencies"]["p95"],
                "winner_consistency": winner_data["latencies"]["consistency"]
            }
        
        return report


async def main():
    """Run benchmark tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Server Benchmarking")
    parser.add_argument("--workload", choices=list(StandardWorkloads.get_all().keys()),
                       default="real_world_mix", help="Workload to run")
    parser.add_argument("--duration", type=int, help="Override workload duration (seconds)")
    parser.add_argument("--compare", action="store_true", help="Compare multiple servers")
    parser.add_argument("--quick", action="store_true", help="Run quick benchmarks")
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(level=logging.WARNING)
    
    runner = BenchmarkRunner()
    
    # Select workload
    if args.quick:
        workloads = StandardWorkloads.get_quick_benchmarks()
        workload = workloads.get("quick_mixed")
    else:
        workloads = StandardWorkloads.get_all()
        workload = workloads[args.workload]
    
    if args.duration:
        workload.duration_seconds = args.duration
    
    # Server configurations
    from config import TEST_DIR
    server_configs = [
        {"name": "filesystem", "type": "filesystem", "path": TEST_DIR}
    ]
    
    if args.compare:
        # Add more server configs for comparison
        # For now, we'll compare the same server with different settings
        server_configs.append(
            {"name": "filesystem_no_retry", "type": "filesystem", "path": TEST_DIR}
        )
        
        report = await runner.compare_servers(server_configs, workload)
        
        print(f"\n{'=' * 60}")
        print("COMPARISON REPORT")
        print(f"{'=' * 60}")
        print(f"Winner: {report['winner']} (Score: {report['summary']['winning_score']:.1f})")
        print(f"\nRankings:")
        for i, (server, score) in enumerate(report["rankings"], 1):
            print(f"  {i}. {server}: {score:.1f}")
        
        print(f"\nDetailed Metrics:")
        for metric, data in report["detailed_comparison"].items():
            print(f"  {metric}:")
            best = data.get("best", "")
            for server, value in data.items():
                if server != "best":
                    marker = " ⭐" if server == best else ""
                    print(f"    {server}: {value:.2f}{marker}")
    else:
        # Single benchmark
        results = await runner.run_benchmark(server_configs[0], workload)
        
        # Save results to JSON
        with open(f"benchmark_{results['benchmark_id']}.json", "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"\nResults saved to benchmark_{results['benchmark_id']}.json")


if __name__ == "__main__":
    asyncio.run(main())