#!/usr/bin/env python3
"""
Real chaos engineering for MCP servers.
Injects actual faults to test resilience.
"""

import asyncio
import random
import time
import sqlite3
import json
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from pathlib import Path
import sys
import logging

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "web" / "backend" / "core"))
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_client import MCPClient
MinimalMCPClient = MCPClient  # Alias for compatibility
from metrics_service import MetricsService

logger = logging.getLogger(__name__)


class ChaosEngine:
    """Real chaos engineering for MCP servers."""
    
    def __init__(self, client: MinimalMCPClient):
        self.client = client
        self.original_methods = {}
        self.metrics = MetricsService("chaos_metrics.db")
        self.chaos_active = False
        self.injection_stats = {
            "latency_injected": 0,
            "errors_injected": 0,
            "timeouts_injected": 0,
            "corruptions_injected": 0
        }
    
    @asynccontextmanager
    async def inject_latency(self, min_ms: int = 100, max_ms: int = 1000, probability: float = 1.0):
        """Inject network latency into operations."""
        original = self.client.call_tool
        self.chaos_active = True
        
        async def delayed_call(name, args):
            if random.random() < probability:
                delay = random.uniform(min_ms, max_ms) / 1000
                logger.info(f"Injecting {delay*1000:.0f}ms latency into {name}")
                await asyncio.sleep(delay)
                self.metrics.record_operation(
                    operation=f"chaos_latency_{name}",
                    duration_ms=delay * 1000,
                    status="injected",
                    tool_name=name
                )
                self.injection_stats["latency_injected"] += 1
            return await original(name, args)
        
        self.client.call_tool = delayed_call
        try:
            yield
        finally:
            self.client.call_tool = original
            self.chaos_active = False
    
    @asynccontextmanager
    async def inject_errors(self, error_rate: float = 0.1, error_types: List[str] = None):
        """Inject various types of errors into operations."""
        if error_types is None:
            error_types = ["generic", "timeout", "connection", "permission"]
        
        original = self.client.call_tool
        self.chaos_active = True
        
        async def faulty_call(name, args):
            if random.random() < error_rate:
                error_type = random.choice(error_types)
                logger.warning(f"Injecting {error_type} error into {name}")
                
                self.metrics.record_operation(
                    operation=f"chaos_error_{name}",
                    duration_ms=0,
                    status="error_injected",
                    tool_name=name,
                    error_msg=error_type
                )
                self.injection_stats["errors_injected"] += 1
                
                if error_type == "timeout":
                    self.injection_stats["timeouts_injected"] += 1
                    await asyncio.sleep(30)  # Simulate timeout
                    raise asyncio.TimeoutError(f"Chaos: Operation {name} timed out")
                elif error_type == "connection":
                    raise ConnectionError(f"Chaos: Connection lost during {name}")
                elif error_type == "permission":
                    raise PermissionError(f"Chaos: Permission denied for {name}")
                else:
                    raise Exception(f"Chaos: Generic error in {name}")
            
            return await original(name, args)
        
        self.client.call_tool = faulty_call
        try:
            yield
        finally:
            self.client.call_tool = original
            self.chaos_active = False
    
    @asynccontextmanager
    async def inject_data_corruption(self, corruption_rate: float = 0.05):
        """Inject data corruption into results."""
        original = self.client.call_tool
        self.chaos_active = True
        
        async def corrupt_call(name, args):
            result = await original(name, args)
            
            if random.random() < corruption_rate:
                logger.warning(f"Corrupting result from {name}")
                self.injection_stats["corruptions_injected"] += 1
                
                # Different corruption strategies
                corruption_type = random.choice(["truncate", "scramble", "nullify"])
                
                if isinstance(result, dict):
                    if corruption_type == "truncate" and "result" in result:
                        if "content" in result["result"]:
                            # Truncate content
                            content = result["result"]["content"]
                            if isinstance(content, list) and content:
                                if "text" in content[0]:
                                    original_text = content[0]["text"]
                                    content[0]["text"] = original_text[:len(original_text)//2]
                    
                    elif corruption_type == "scramble" and "result" in result:
                        # Scramble some data
                        result["result"] = {"corrupted": True, "original_keys": list(result.get("result", {}).keys())}
                    
                    elif corruption_type == "nullify":
                        # Remove result
                        if "result" in result:
                            del result["result"]
                
                self.metrics.record_operation(
                    operation=f"chaos_corruption_{name}",
                    duration_ms=0,
                    status="corrupted",
                    tool_name=name,
                    metadata={"corruption_type": corruption_type}
                )
            
            return result
        
        self.client.call_tool = corrupt_call
        try:
            yield
        finally:
            self.client.call_tool = original
            self.chaos_active = False
    
    @asynccontextmanager
    async def inject_resource_exhaustion(self, memory_mb: int = 100, cpu_iterations: int = 1000000):
        """Simulate resource exhaustion."""
        self.chaos_active = True
        
        # Allocate memory
        memory_hog = []
        try:
            for _ in range(memory_mb):
                memory_hog.append(bytearray(1024 * 1024))  # 1MB chunks
            
            # CPU burn
            def cpu_burn():
                result = 0
                for i in range(cpu_iterations):
                    result += i ** 2
                return result
            
            # Run CPU burn in background
            loop = asyncio.get_event_loop()
            burn_task = loop.run_in_executor(None, cpu_burn)
            
            yield
            
        finally:
            # Cleanup
            memory_hog.clear()
            self.chaos_active = False
    
    async def run_chaos_test(self, test_operations: List[Dict[str, Any]], fault_config: Dict[str, Any]):
        """Run a comprehensive chaos test with multiple phases."""
        results = {
            "test_id": f"chaos_{int(time.time())}",
            "phases": {},
            "injection_stats": {},
            "resilience_metrics": {}
        }
        
        # Phase 1: Baseline (no chaos)
        print("\n" + "=" * 50)
        print("PHASE 1: BASELINE MEASUREMENT")
        print("=" * 50)
        
        baseline_results = await self._run_operations(test_operations, "baseline")
        results["phases"]["baseline"] = baseline_results
        
        # Phase 2: Latency injection
        print("\n" + "=" * 50)
        print("PHASE 2: LATENCY INJECTION")
        print("=" * 50)
        
        latency_config = fault_config.get("latency", {"min_ms": 100, "max_ms": 500, "probability": 0.5})
        async with self.inject_latency(**latency_config):
            latency_results = await self._run_operations(test_operations, "latency")
            results["phases"]["latency"] = latency_results
        
        # Phase 3: Error injection
        print("\n" + "=" * 50)
        print("PHASE 3: ERROR INJECTION")
        print("=" * 50)
        
        error_config = fault_config.get("errors", {"error_rate": 0.2})
        async with self.inject_errors(**error_config):
            error_results = await self._run_operations(test_operations, "errors")
            results["phases"]["errors"] = error_results
        
        # Phase 4: Combined chaos
        print("\n" + "=" * 50)
        print("PHASE 4: COMBINED CHAOS")
        print("=" * 50)
        
        async with self.inject_latency(min_ms=50, max_ms=200, probability=0.3):
            async with self.inject_errors(error_rate=0.1):
                async with self.inject_data_corruption(corruption_rate=0.05):
                    combined_results = await self._run_operations(test_operations, "combined")
                    results["phases"]["combined"] = combined_results
        
        # Phase 5: Recovery verification
        print("\n" + "=" * 50)
        print("PHASE 5: RECOVERY VERIFICATION")
        print("=" * 50)
        
        await asyncio.sleep(2)  # Let system stabilize
        recovery_results = await self._run_operations(test_operations, "recovery")
        results["phases"]["recovery"] = recovery_results
        
        # Calculate resilience score
        results["resilience_metrics"] = self._calculate_resilience(results["phases"])
        results["injection_stats"] = self.injection_stats.copy()
        
        # Store results
        self._store_chaos_results(results)
        
        return results
    
    async def _run_operations(self, operations: List[Dict[str, Any]], phase: str) -> Dict:
        """Run a set of operations and collect metrics."""
        phase_start = time.time()
        successes = 0
        failures = 0
        errors = []
        latencies = []
        
        for op in operations:
            op_start = time.time()
            try:
                result = await self.client.call_tool(op["tool"], op.get("args", {}))
                if "result" in result:
                    successes += 1
                else:
                    failures += 1
                    errors.append(f"{op['tool']}: No result in response")
            except Exception as e:
                failures += 1
                errors.append(f"{op['tool']}: {str(e)[:50]}")
            
            latencies.append((time.time() - op_start) * 1000)
        
        phase_duration = time.time() - phase_start
        
        return {
            "phase": phase,
            "duration_s": phase_duration,
            "operations": len(operations),
            "successes": successes,
            "failures": failures,
            "success_rate": successes / len(operations) if operations else 0,
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
            "max_latency_ms": max(latencies) if latencies else 0,
            "errors": errors[:5]  # First 5 errors
        }
    
    def _calculate_resilience(self, phases: Dict) -> Dict:
        """Calculate resilience metrics from test phases."""
        baseline = phases.get("baseline", {})
        combined = phases.get("combined", {})
        recovery = phases.get("recovery", {})
        
        baseline_success = baseline.get("success_rate", 0)
        chaos_success = combined.get("success_rate", 0)
        recovery_success = recovery.get("success_rate", 0)
        
        # Resilience score (0-100)
        if baseline_success > 0:
            degradation_score = (chaos_success / baseline_success) * 50
            recovery_score = (recovery_success / baseline_success) * 50
            resilience_score = min(degradation_score + recovery_score, 100)
        else:
            resilience_score = 0
        
        # Performance impact
        baseline_latency = baseline.get("avg_latency_ms", 0)
        chaos_latency = combined.get("avg_latency_ms", 0)
        
        if baseline_latency > 0:
            performance_impact = ((chaos_latency - baseline_latency) / baseline_latency) * 100
        else:
            performance_impact = 0
        
        return {
            "resilience_score": resilience_score,
            "degradation": (1 - chaos_success / baseline_success) * 100 if baseline_success > 0 else 100,
            "recovery_rate": recovery_success * 100,
            "performance_impact": performance_impact,
            "chaos_tolerance": chaos_success * 100,
            "grade": self._score_to_grade(resilience_score)
        }
    
    def _score_to_grade(self, score: float) -> str:
        """Convert resilience score to letter grade."""
        if score >= 90: return "A"
        if score >= 80: return "B"
        if score >= 70: return "C"
        if score >= 60: return "D"
        return "F"
    
    def _store_chaos_results(self, results: Dict):
        """Store chaos test results in database."""
        conn = sqlite3.connect("chaos_results.db")
        conn.execute('''
            CREATE TABLE IF NOT EXISTS chaos_tests (
                test_id TEXT PRIMARY KEY,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                resilience_score REAL,
                grade TEXT,
                phases TEXT,
                injection_stats TEXT,
                metrics TEXT
            )
        ''')
        
        conn.execute('''
            INSERT INTO chaos_tests (test_id, resilience_score, grade, phases, injection_stats, metrics)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            results["test_id"],
            results["resilience_metrics"]["resilience_score"],
            results["resilience_metrics"]["grade"],
            json.dumps(results["phases"]),
            json.dumps(results["injection_stats"]),
            json.dumps(results["resilience_metrics"])
        ))
        
        conn.commit()
        conn.close()


# Test the chaos engine
async def test_chaos_engine():
    """Test the chaos engineering framework."""
    print("=" * 60)
    print("CHAOS ENGINEERING TEST")
    print("=" * 60)
    
    # Initialize client
    client = MCPClient()  # Use expanded client with retry
    await client.connect_filesystem("/private/tmp")
    
    # Initialize chaos engine
    chaos = ChaosEngine(client)
    
    # Define test operations
    test_operations = [
        {"tool": "write_file", "args": {"path": "/private/tmp/chaos_test_1.txt", "content": "Test 1"}},
        {"tool": "read_text_file", "args": {"path": "/private/tmp/chaos_test_1.txt"}},
        {"tool": "list_directory", "args": {"path": "/private/tmp"}},
        {"tool": "create_directory", "args": {"path": "/private/tmp/chaos_test_dir"}},
        {"tool": "write_file", "args": {"path": "/private/tmp/chaos_test_2.txt", "content": "Test 2"}},
    ]
    
    # Define fault configuration
    fault_config = {
        "latency": {
            "min_ms": 100,
            "max_ms": 500,
            "probability": 0.5
        },
        "errors": {
            "error_rate": 0.2,
            "error_types": ["timeout", "connection", "generic"]
        }
    }
    
    # Run chaos test
    results = await chaos.run_chaos_test(test_operations, fault_config)
    
    # Print results
    print("\n" + "=" * 60)
    print("CHAOS TEST RESULTS")
    print("=" * 60)
    
    print(f"\nResilience Score: {results['resilience_metrics']['resilience_score']:.1f}/100")
    print(f"Grade: {results['resilience_metrics']['grade']}")
    print(f"Degradation: {results['resilience_metrics']['degradation']:.1f}%")
    print(f"Recovery Rate: {results['resilience_metrics']['recovery_rate']:.1f}%")
    print(f"Performance Impact: {results['resilience_metrics']['performance_impact']:.1f}%")
    
    print("\nInjection Statistics:")
    for stat, value in results["injection_stats"].items():
        print(f"  {stat}: {value}")
    
    print("\nPhase Results:")
    for phase_name, phase_data in results["phases"].items():
        print(f"  {phase_name.upper()}:")
        print(f"    Success rate: {phase_data['success_rate']*100:.1f}%")
        print(f"    Avg latency: {phase_data['avg_latency_ms']:.1f}ms")
    
    # Cleanup
    await client.close()
    
    return results


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    asyncio.run(test_chaos_engine())