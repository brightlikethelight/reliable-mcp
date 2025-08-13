#!/usr/bin/env python3
"""
Real Reliability Metrics for MCP Servers
Measures actual reliability indicators: MTBF, recovery time, stability.
Goes beyond simple performance metrics to measure production readiness.
"""

import asyncio
import time
import statistics
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from mcp_client import MCPClient
from config import SERVERS, TEST_DIR


class FailureType(Enum):
    """Types of failures we track."""
    STARTUP = "startup_failure"
    CONNECTION = "connection_lost"
    TIMEOUT = "operation_timeout"
    ERROR = "operation_error"
    CRASH = "server_crash"
    RESOURCE = "resource_exhaustion"


@dataclass
class FailureEvent:
    """A recorded failure event."""
    timestamp: float
    failure_type: FailureType
    description: str
    recovery_time: Optional[float] = None
    recovered: bool = False


@dataclass
class ReliabilityMetrics:
    """Comprehensive reliability metrics."""
    # Basic info
    server_name: str
    test_duration: float
    total_operations: int
    
    # Reliability metrics
    mtbf: float  # Mean Time Between Failures (seconds)
    mttr: float  # Mean Time To Recovery (seconds)
    availability: float  # Percentage (0-100)
    reliability_score: float  # Overall score (0-100)
    
    # Stability metrics
    connection_stability: float  # Percentage of time connected
    operation_success_rate: float  # Percentage of successful operations
    crash_count: int
    timeout_count: int
    error_count: int
    
    # Recovery metrics
    recovery_success_rate: float  # Percentage of successful recoveries
    avg_recovery_time: float  # Average recovery time in seconds
    max_recovery_time: float  # Worst case recovery time
    
    # Detailed data
    failures: List[FailureEvent] = field(default_factory=list)
    uptime_periods: List[Tuple[float, float]] = field(default_factory=list)


class ReliabilityTester:
    """Test MCP server reliability over extended periods."""
    
    def __init__(self):
        self.failures = []
        self.uptime_periods = []
        self.current_uptime_start = None
        self.operation_count = 0
        self.successful_operations = 0
        self.test_start_time = None
    
    async def test_reliability(
        self,
        server_name: str,
        duration_minutes: int = 5,
        operations_per_minute: int = 60
    ) -> ReliabilityMetrics:
        """Run extended reliability test."""
        
        print(f"\n{'=' * 60}")
        print(f"RELIABILITY TEST: {server_name}")
        print(f"Duration: {duration_minutes} minutes")
        print(f"Load: {operations_per_minute} ops/minute")
        print(f"{'=' * 60}")
        
        self.failures = []
        self.uptime_periods = []
        self.operation_count = 0
        self.successful_operations = 0
        self.test_start_time = time.time()
        
        test_end_time = self.test_start_time + (duration_minutes * 60)
        operation_interval = 60 / operations_per_minute
        
        client = None
        last_progress = 0
        
        while time.time() < test_end_time:
            elapsed = time.time() - self.test_start_time
            progress = int((elapsed / (duration_minutes * 60)) * 100)
            
            if progress >= last_progress + 10:
                print(f"\nProgress: {progress}% - {len(self.failures)} failures recorded")
                last_progress = progress
            
            # Start server if not running
            if client is None:
                client = await self._start_server(server_name)
                if client is None:
                    await asyncio.sleep(5)  # Wait before retry
                    continue
            
            # Perform operation
            success = await self._perform_operation(client)
            
            if not success:
                # Server might have crashed
                await self._handle_failure(client, FailureType.ERROR)
                client = await self._attempt_recovery(server_name)
            
            # Wait for next operation
            await asyncio.sleep(operation_interval)
        
        # Clean up
        if client:
            self._record_uptime_end()
            await client.stop()
        
        # Calculate metrics
        return self._calculate_metrics(server_name, duration_minutes * 60)
    
    async def test_recovery(self, server_name: str) -> Dict:
        """Test server recovery capabilities."""
        print(f"\n{'=' * 60}")
        print(f"RECOVERY TEST: {server_name}")
        print(f"{'=' * 60}")
        
        recovery_times = []
        recovery_methods = {
            "restart": 0,
            "reconnect": 0,
            "reset": 0
        }
        
        # Test different failure scenarios
        scenarios = [
            ("normal_stop", self._test_normal_stop_recovery),
            ("force_kill", self._test_force_kill_recovery),
            ("network_disconnect", self._test_network_recovery),
            ("resource_exhaustion", self._test_resource_recovery)
        ]
        
        for scenario_name, test_func in scenarios:
            print(f"\nTesting {scenario_name}...")
            recovery_time, method = await test_func(server_name)
            
            if recovery_time is not None:
                recovery_times.append(recovery_time)
                recovery_methods[method] += 1
                print(f"  └─ Recovered in {recovery_time:.2f}s using {method}")
            else:
                print(f"  └─ Failed to recover")
        
        return {
            "avg_recovery_time": statistics.mean(recovery_times) if recovery_times else None,
            "max_recovery_time": max(recovery_times) if recovery_times else None,
            "min_recovery_time": min(recovery_times) if recovery_times else None,
            "recovery_success_rate": len(recovery_times) / len(scenarios) * 100,
            "recovery_methods": recovery_methods
        }
    
    async def test_stability(self, server_name: str, duration_minutes: int = 10) -> Dict:
        """Test server stability under constant load."""
        print(f"\n{'=' * 60}")
        print(f"STABILITY TEST: {server_name}")
        print(f"Duration: {duration_minutes} minutes")
        print(f"{'=' * 60}")
        
        client = MCPClient(server_name)
        await client.start()
        
        stability_scores = []
        response_times = []
        test_start = time.time()
        test_end = test_start + (duration_minutes * 60)
        
        operations = 0
        errors = 0
        
        while time.time() < test_end:
            batch_start = time.time()
            batch_times = []
            
            # Run batch of operations
            for _ in range(10):
                op_start = time.time()
                try:
                    tools = await asyncio.wait_for(
                        client.list_tools(),
                        timeout=2.0
                    )
                    batch_times.append(time.time() - op_start)
                    operations += 1
                except:
                    errors += 1
            
            if batch_times:
                # Calculate stability as inverse of variance
                mean_time = statistics.mean(batch_times)
                if len(batch_times) > 1:
                    variance = statistics.variance(batch_times)
                    stability = 100 / (1 + variance * 100)
                else:
                    stability = 100
                
                stability_scores.append(stability)
                response_times.extend(batch_times)
            
            # Progress update
            elapsed = time.time() - test_start
            if int(elapsed) % 60 == 0:
                error_rate = (errors / max(operations, 1)) * 100
                print(f"  {int(elapsed/60)} min: {operations} ops, {error_rate:.1f}% errors")
            
            await asyncio.sleep(1)
        
        await client.stop()
        
        return {
            "avg_stability": statistics.mean(stability_scores) if stability_scores else 0,
            "min_stability": min(stability_scores) if stability_scores else 0,
            "max_stability": max(stability_scores) if stability_scores else 0,
            "avg_response_time": statistics.mean(response_times) if response_times else 0,
            "error_rate": (errors / max(operations, 1)) * 100,
            "total_operations": operations
        }
    
    async def _start_server(self, server_name: str) -> Optional[MCPClient]:
        """Start server and track uptime."""
        try:
            client = MCPClient(server_name)
            await asyncio.wait_for(client.start(), timeout=10)
            self._record_uptime_start()
            return client
        except Exception as e:
            self._record_failure(FailureType.STARTUP, str(e))
            return None
    
    async def _perform_operation(self, client: MCPClient) -> bool:
        """Perform a test operation."""
        self.operation_count += 1
        
        try:
            # Simple operation - list tools
            tools = await asyncio.wait_for(
                client.list_tools(),
                timeout=5.0
            )
            self.successful_operations += 1
            return True
            
        except asyncio.TimeoutError:
            self._record_failure(FailureType.TIMEOUT, "Operation timed out")
            return False
        except Exception as e:
            self._record_failure(FailureType.ERROR, str(e))
            return False
    
    async def _handle_failure(self, client: MCPClient, failure_type: FailureType):
        """Handle a failure event."""
        self._record_uptime_end()
        
        try:
            await client.stop()
        except:
            pass
    
    async def _attempt_recovery(self, server_name: str) -> Optional[MCPClient]:
        """Attempt to recover from failure."""
        recovery_start = time.time()
        
        # Try to restart
        client = await self._start_server(server_name)
        
        if client and self.failures:
            recovery_time = time.time() - recovery_start
            self.failures[-1].recovery_time = recovery_time
            self.failures[-1].recovered = True
        
        return client
    
    async def _test_normal_stop_recovery(self, server_name: str) -> Tuple[Optional[float], str]:
        """Test recovery from normal stop."""
        client = MCPClient(server_name)
        
        try:
            await client.start()
            await client.stop()
            
            start_time = time.time()
            await client.start()
            recovery_time = time.time() - start_time
            
            await client.stop()
            return recovery_time, "restart"
            
        except:
            return None, "failed"
    
    async def _test_force_kill_recovery(self, server_name: str) -> Tuple[Optional[float], str]:
        """Test recovery from force kill."""
        client = MCPClient(server_name)
        
        try:
            await client.start()
            
            # Force kill the process
            if client.process:
                client.process.kill()
            
            start_time = time.time()
            client = MCPClient(server_name)
            await client.start()
            recovery_time = time.time() - start_time
            
            await client.stop()
            return recovery_time, "restart"
            
        except:
            return None, "failed"
    
    async def _test_network_recovery(self, server_name: str) -> Tuple[Optional[float], str]:
        """Test recovery from network issues."""
        # Simulate by timeout
        client = MCPClient(server_name)
        
        try:
            await client.start()
            
            # Simulate network issue
            client.process = None
            
            start_time = time.time()
            await client.start()
            recovery_time = time.time() - start_time
            
            await client.stop()
            return recovery_time, "reconnect"
            
        except:
            return None, "failed"
    
    async def _test_resource_recovery(self, server_name: str) -> Tuple[Optional[float], str]:
        """Test recovery from resource exhaustion."""
        client = MCPClient(server_name)
        
        try:
            await client.start()
            
            # Simulate resource exhaustion with many operations
            tasks = []
            for _ in range(100):
                tasks.append(client.list_tools())
            
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=5
                )
            except:
                pass
            
            start_time = time.time()
            # Try to recover
            await client.stop()
            client = MCPClient(server_name)
            await client.start()
            recovery_time = time.time() - start_time
            
            await client.stop()
            return recovery_time, "reset"
            
        except:
            return None, "failed"
    
    def _record_failure(self, failure_type: FailureType, description: str):
        """Record a failure event."""
        self.failures.append(FailureEvent(
            timestamp=time.time(),
            failure_type=failure_type,
            description=description
        ))
    
    def _record_uptime_start(self):
        """Record start of uptime period."""
        self.current_uptime_start = time.time()
    
    def _record_uptime_end(self):
        """Record end of uptime period."""
        if self.current_uptime_start:
            self.uptime_periods.append((
                self.current_uptime_start,
                time.time()
            ))
            self.current_uptime_start = None
    
    def _calculate_metrics(self, server_name: str, test_duration: float) -> ReliabilityMetrics:
        """Calculate reliability metrics from test data."""
        
        # MTBF - Mean Time Between Failures
        if len(self.failures) > 1:
            failure_intervals = []
            for i in range(1, len(self.failures)):
                interval = self.failures[i].timestamp - self.failures[i-1].timestamp
                failure_intervals.append(interval)
            mtbf = statistics.mean(failure_intervals)
        elif len(self.failures) == 1:
            mtbf = test_duration  # One failure in entire test
        else:
            mtbf = test_duration * 2  # No failures (estimate)
        
        # MTTR - Mean Time To Recovery
        recovery_times = [f.recovery_time for f in self.failures if f.recovery_time]
        mttr = statistics.mean(recovery_times) if recovery_times else 0
        
        # Availability
        total_uptime = sum(end - start for start, end in self.uptime_periods)
        availability = (total_uptime / test_duration) * 100 if test_duration > 0 else 0
        
        # Connection stability
        connection_stability = availability  # Same as availability for now
        
        # Operation success rate
        operation_success_rate = (self.successful_operations / max(self.operation_count, 1)) * 100
        
        # Count failures by type
        crash_count = len([f for f in self.failures if f.failure_type == FailureType.CRASH])
        timeout_count = len([f for f in self.failures if f.failure_type == FailureType.TIMEOUT])
        error_count = len([f for f in self.failures if f.failure_type == FailureType.ERROR])
        
        # Recovery metrics
        recovered_count = len([f for f in self.failures if f.recovered])
        recovery_success_rate = (recovered_count / max(len(self.failures), 1)) * 100
        
        avg_recovery_time = statistics.mean(recovery_times) if recovery_times else 0
        max_recovery_time = max(recovery_times) if recovery_times else 0
        
        # Overall reliability score (0-100)
        reliability_score = self._calculate_reliability_score(
            availability, operation_success_rate, mtbf, test_duration
        )
        
        return ReliabilityMetrics(
            server_name=server_name,
            test_duration=test_duration,
            total_operations=self.operation_count,
            mtbf=mtbf,
            mttr=mttr,
            availability=availability,
            reliability_score=reliability_score,
            connection_stability=connection_stability,
            operation_success_rate=operation_success_rate,
            crash_count=crash_count,
            timeout_count=timeout_count,
            error_count=error_count,
            recovery_success_rate=recovery_success_rate,
            avg_recovery_time=avg_recovery_time,
            max_recovery_time=max_recovery_time,
            failures=self.failures,
            uptime_periods=self.uptime_periods
        )
    
    def _calculate_reliability_score(
        self,
        availability: float,
        success_rate: float,
        mtbf: float,
        test_duration: float
    ) -> float:
        """Calculate overall reliability score."""
        
        # Weighted scoring
        availability_weight = 0.3
        success_weight = 0.3
        mtbf_weight = 0.4
        
        # Normalize MTBF (assume 1 hour between failures is excellent)
        mtbf_score = min(100, (mtbf / 3600) * 100)
        
        score = (
            availability * availability_weight +
            success_rate * success_weight +
            mtbf_score * mtbf_weight
        )
        
        return min(100, max(0, score))


def print_reliability_report(metrics: ReliabilityMetrics):
    """Print formatted reliability report."""
    print("\n" + "=" * 60)
    print("RELIABILITY METRICS REPORT")
    print("=" * 60)
    print(f"Server: {metrics.server_name}")
    print(f"Test Duration: {metrics.test_duration/60:.1f} minutes")
    print(f"Total Operations: {metrics.total_operations}")
    
    print("\n📊 KEY METRICS:")
    print(f"  Reliability Score: {metrics.reliability_score:.1f}/100")
    print(f"  Availability: {metrics.availability:.2f}%")
    print(f"  Success Rate: {metrics.operation_success_rate:.2f}%")
    
    print("\n⏱ FAILURE & RECOVERY:")
    print(f"  MTBF: {metrics.mtbf:.1f} seconds")
    print(f"  MTTR: {metrics.mttr:.1f} seconds")
    print(f"  Recovery Success: {metrics.recovery_success_rate:.1f}%")
    
    print("\n📈 STABILITY:")
    print(f"  Connection Stability: {metrics.connection_stability:.2f}%")
    print(f"  Failures: {len(metrics.failures)}")
    print(f"    - Crashes: {metrics.crash_count}")
    print(f"    - Timeouts: {metrics.timeout_count}")
    print(f"    - Errors: {metrics.error_count}")
    
    # Reliability grade
    if metrics.reliability_score >= 95:
        grade = "A+ (Production Ready)"
    elif metrics.reliability_score >= 90:
        grade = "A (Excellent)"
    elif metrics.reliability_score >= 80:
        grade = "B (Good)"
    elif metrics.reliability_score >= 70:
        grade = "C (Acceptable)"
    elif metrics.reliability_score >= 60:
        grade = "D (Poor)"
    else:
        grade = "F (Unreliable)"
    
    print(f"\n🏆 GRADE: {grade}")
    print("=" * 60)


async def main():
    """Run reliability tests."""
    import sys
    
    # Get server name from command line
    server_name = sys.argv[1] if len(sys.argv) > 1 else "filesystem"
    
    if server_name not in SERVERS:
        print(f"Unknown server: {server_name}")
        return 1
    
    tester = ReliabilityTester()
    
    # Quick reliability test (2 minutes)
    print("Running quick reliability test (2 minutes)...")
    metrics = await tester.test_reliability(server_name, duration_minutes=2)
    print_reliability_report(metrics)
    
    # Save report
    import json
    with open(f"reliability_report_{server_name}.json", "w") as f:
        json.dump({
            "server": metrics.server_name,
            "reliability_score": metrics.reliability_score,
            "availability": metrics.availability,
            "mtbf": metrics.mtbf,
            "mttr": metrics.mttr,
            "operation_success_rate": metrics.operation_success_rate,
            "failures": len(metrics.failures)
        }, f, indent=2)
    
    print(f"\nReport saved to reliability_report_{server_name}.json")
    
    return 0 if metrics.reliability_score >= 70 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    import sys
    sys.exit(exit_code)