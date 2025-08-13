#!/usr/bin/env python3
"""
Measure ACTUAL reliability of MCP servers.
This provides real metrics about MCP server performance and reliability.
"""

import asyncio
import time
import statistics
from typing import List, Dict, Any, Optional
from pathlib import Path
import sys
import json
from datetime import datetime
import sqlite3

# Import our working client
sys.path.insert(0, str(Path(__file__).parent))
from mcp_client import MCPClient
MinimalMCPClient = MCPClient  # Alias for compatibility
from fault_injection_real import RealFaultInjector


class ReliabilityMeasurement:
    """Measure ACTUAL reliability of MCP servers."""
    
    def __init__(self):
        self.results = []
        self.db_path = "reliability_metrics.db"
        self._init_db()
    
    def _init_db(self):
        """Initialize reliability metrics database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS reliability_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_name TEXT NOT NULL,
                total_operations INTEGER,
                successful_operations INTEGER,
                failed_operations INTEGER,
                reliability_score REAL,
                p50_latency_ms REAL,
                p95_latency_ms REAL,
                p99_latency_ms REAL,
                min_latency_ms REAL,
                max_latency_ms REAL,
                mean_latency_ms REAL,
                fault_injection TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    
    async def measure_baseline_reliability(self, 
                                          operations: List[Dict[str, Any]], 
                                          iterations: int = 100) -> Dict:
        """Measure baseline reliability without faults."""
        print("\n" + "=" * 60)
        print("BASELINE RELIABILITY MEASUREMENT")
        print("=" * 60)
        
        client = MinimalMCPClient()
        await client.connect_filesystem("/private/tmp")
        
        results = {
            "success": 0,
            "failure": 0,
            "latencies": [],
            "errors": []
        }
        
        total_ops = iterations * len(operations)
        print(f"Running {total_ops} operations ({iterations} iterations × {len(operations)} ops)...")
        
        for i in range(iterations):
            if i % 10 == 0:
                print(f"  Progress: {i}/{iterations} iterations...")
            
            for op in operations:
                start = time.time()
                try:
                    await client.call_tool(op["tool"], op["args"])
                    results["success"] += 1
                    latency = (time.time() - start) * 1000  # ms
                    results["latencies"].append(latency)
                except Exception as e:
                    results["failure"] += 1
                    results["errors"].append(str(e))
        
        await client.close()
        
        # Calculate metrics
        metrics = self._calculate_metrics(results, "baseline", total_ops)
        self._store_metrics(metrics, "baseline", None)
        self._print_metrics(metrics)
        
        return metrics
    
    async def measure_with_fault_injection(self,
                                          operations: List[Dict[str, Any]],
                                          iterations: int = 100,
                                          error_rate: float = 0.1,
                                          latency_range: tuple = (100, 500)) -> Dict:
        """Measure reliability with fault injection."""
        print("\n" + "=" * 60)
        print("RELIABILITY WITH FAULT INJECTION")
        print("=" * 60)
        
        client = MCPClient()  # Use expanded client with retry
        await client.connect_filesystem("/private/tmp")
        
        # Inject faults
        injector = RealFaultInjector(client)
        injector.inject_combined_faults(
            error_rate=error_rate,
            latency_rate=0.2,
            timeout_rate=0.02,
            corruption_rate=0.02
        )
        
        results = {
            "success": 0,
            "failure": 0,
            "latencies": [],
            "errors": [],
            "retries": 0
        }
        
        total_ops = iterations * len(operations)
        print(f"Running {total_ops} operations with {error_rate*100}% error rate...")
        print(f"Fault configuration: errors={error_rate}, latency=0.2, timeout=0.02, corruption=0.02")
        
        for i in range(iterations):
            if i % 10 == 0:
                print(f"  Progress: {i}/{iterations} iterations...")
            
            for op in operations:
                start = time.time()
                try:
                    # Use retry method
                    await client.call_tool_with_retry(op["tool"], op["args"], retries=3)
                    results["success"] += 1
                    latency = (time.time() - start) * 1000
                    results["latencies"].append(latency)
                except Exception as e:
                    results["failure"] += 1
                    results["errors"].append(str(e))
        
        # Get fault injection stats
        fault_stats = injector.get_stats()
        print(f"\nFault injection stats: {fault_stats}")
        
        await client.close()
        
        # Calculate metrics
        metrics = self._calculate_metrics(results, "with_faults", total_ops)
        metrics["fault_stats"] = fault_stats
        
        fault_config = {
            "error_rate": error_rate,
            "latency_rate": 0.2,
            "timeout_rate": 0.02,
            "corruption_rate": 0.02
        }
        self._store_metrics(metrics, "with_faults", json.dumps(fault_config))
        self._print_metrics(metrics)
        
        return metrics
    
    async def measure_scaling_reliability(self, 
                                        operations: List[Dict[str, Any]],
                                        scale_factors: List[int] = [1, 5, 10, 20]) -> Dict:
        """Measure how reliability changes with scale."""
        print("\n" + "=" * 60)
        print("SCALING RELIABILITY MEASUREMENT")
        print("=" * 60)
        
        scaling_results = {}
        
        for scale in scale_factors:
            print(f"\n--- Testing with scale factor {scale}x ---")
            
            client = MinimalMCPClient()
            await client.connect_filesystem("/private/tmp")
            
            results = {
                "success": 0,
                "failure": 0,
                "latencies": [],
                "errors": []
            }
            
            # Run concurrent operations
            async def run_operation(op, index):
                start = time.time()
                try:
                    await client.call_tool(op["tool"], op["args"])
                    return ("success", (time.time() - start) * 1000)
                except Exception as e:
                    return ("failure", str(e))
            
            # Run operations in batches
            batch_size = scale
            total_batches = 10
            
            for batch in range(total_batches):
                tasks = []
                for _ in range(batch_size):
                    for op in operations:
                        tasks.append(run_operation(op, batch * batch_size))
                
                # Run batch concurrently
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in batch_results:
                    if isinstance(result, tuple):
                        if result[0] == "success":
                            results["success"] += 1
                            results["latencies"].append(result[1])
                        else:
                            results["failure"] += 1
                            results["errors"].append(result[1])
                    else:
                        results["failure"] += 1
                        results["errors"].append(str(result))
                
                print(f"    Batch {batch+1}/{total_batches} complete")
            
            await client.close()
            
            # Calculate metrics for this scale
            total_ops = batch_size * total_batches * len(operations)
            metrics = self._calculate_metrics(results, f"scale_{scale}x", total_ops)
            self._store_metrics(metrics, f"scale_{scale}x", json.dumps({"scale": scale}))
            
            scaling_results[f"{scale}x"] = metrics
            
            print(f"\n  Scale {scale}x Results:")
            print(f"    Reliability: {metrics['reliability_score']:.2%}")
            print(f"    P95 Latency: {metrics['p95_latency']:.2f}ms")
        
        return scaling_results
    
    def _calculate_metrics(self, results: Dict, test_name: str, total_ops: int) -> Dict:
        """Calculate reliability metrics."""
        if not results["latencies"]:
            results["latencies"] = [0]  # Prevent empty list errors
        
        sorted_latencies = sorted(results["latencies"])
        
        metrics = {
            "test_name": test_name,
            "total_operations": total_ops,
            "successful": results["success"],
            "failed": results["failure"],
            "reliability_score": results["success"] / total_ops if total_ops > 0 else 0,
            "p50_latency": sorted_latencies[int(len(sorted_latencies) * 0.50)] if sorted_latencies else 0,
            "p95_latency": sorted_latencies[int(len(sorted_latencies) * 0.95)] if sorted_latencies else 0,
            "p99_latency": sorted_latencies[int(len(sorted_latencies) * 0.99)] if sorted_latencies else 0,
            "min_latency": min(sorted_latencies) if sorted_latencies else 0,
            "max_latency": max(sorted_latencies) if sorted_latencies else 0,
            "mean_latency": statistics.mean(sorted_latencies) if sorted_latencies else 0,
            "timestamp": datetime.now().isoformat()
        }
        
        if results["errors"]:
            # Count error types
            error_counts = {}
            for error in results["errors"]:
                error_type = error.split(":")[0] if ":" in error else error
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
            metrics["error_distribution"] = error_counts
        
        return metrics
    
    def _store_metrics(self, metrics: Dict, test_name: str, fault_config: Optional[str]):
        """Store metrics in database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            INSERT INTO reliability_tests 
            (test_name, total_operations, successful_operations, failed_operations,
             reliability_score, p50_latency_ms, p95_latency_ms, p99_latency_ms,
             min_latency_ms, max_latency_ms, mean_latency_ms, fault_injection)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            test_name,
            metrics["total_operations"],
            metrics["successful"],
            metrics["failed"],
            metrics["reliability_score"],
            metrics["p50_latency"],
            metrics["p95_latency"],
            metrics["p99_latency"],
            metrics["min_latency"],
            metrics["max_latency"],
            metrics["mean_latency"],
            fault_config
        ))
        conn.commit()
        conn.close()
    
    def _print_metrics(self, metrics: Dict):
        """Print metrics in a readable format."""
        print(f"\nReliability Metrics:")
        print(f"  Total Operations: {metrics['total_operations']}")
        print(f"  Successful: {metrics['successful']}")
        print(f"  Failed: {metrics['failed']}")
        print(f"  Reliability Score: {metrics['reliability_score']:.2%}")
        print(f"\nLatency Metrics (ms):")
        print(f"  P50: {metrics['p50_latency']:.2f}")
        print(f"  P95: {metrics['p95_latency']:.2f}")
        print(f"  P99: {metrics['p99_latency']:.2f}")
        print(f"  Min: {metrics['min_latency']:.2f}")
        print(f"  Max: {metrics['max_latency']:.2f}")
        print(f"  Mean: {metrics['mean_latency']:.2f}")
        
        if "error_distribution" in metrics:
            print(f"\nError Distribution:")
            for error_type, count in metrics["error_distribution"].items():
                print(f"    {error_type}: {count}")


async def main():
    """Run comprehensive reliability measurements."""
    print("=" * 60)
    print("MCP SERVER RELIABILITY MEASUREMENT")
    print("=" * 60)
    
    # Define test operations
    test_operations = [
        {"tool": "write_file", "args": {"path": "/private/tmp/rel_test.txt", "content": "test"}},
        {"tool": "read_text_file", "args": {"path": "/private/tmp/rel_test.txt"}},
        {"tool": "list_directory", "args": {"path": "/private/tmp"}}
    ]
    
    measurement = ReliabilityMeasurement()
    
    # 1. Baseline reliability
    baseline = await measurement.measure_baseline_reliability(test_operations, iterations=20)
    
    # 2. Reliability with faults
    with_faults = await measurement.measure_with_fault_injection(
        test_operations, 
        iterations=20,
        error_rate=0.15
    )
    
    # 3. Scaling reliability
    scaling = await measurement.measure_scaling_reliability(
        test_operations,
        scale_factors=[1, 2, 4]
    )
    
    # Summary
    print("\n" + "=" * 60)
    print("RELIABILITY MEASUREMENT SUMMARY")
    print("=" * 60)
    print(f"\nBaseline Reliability: {baseline['reliability_score']:.2%}")
    print(f"With Faults (15% error rate): {with_faults['reliability_score']:.2%}")
    print(f"\nScaling Impact:")
    for scale, metrics in scaling.items():
        print(f"  {scale}: {metrics['reliability_score']:.2%} reliability, {metrics['p95_latency']:.2f}ms P95")
    
    print(f"\n✅ Reliability metrics saved to reliability_metrics.db")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())