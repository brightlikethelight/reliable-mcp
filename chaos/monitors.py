"""Monitoring components for chaos engineering experiments."""

import asyncio
import time
import psutil
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from collections import deque, defaultdict
import logging

from opentelemetry import trace, metrics
from opentelemetry.metrics import Observation

from .faults import FaultInjector


logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Metrics
monitor_observations = meter.create_counter(
    "chaos.monitor_observations",
    description="Number of monitoring observations"
)
health_check_duration = meter.create_histogram(
    "chaos.health_check_duration",
    description="Duration of health checks",
    unit="ms"
)


class MetricsCollector:
    """Collects and aggregates metrics during chaos experiments."""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self.counters: Dict[str, int] = defaultdict(int)
        self.start_time = time.time()
        
    def record_value(self, metric_name: str, value: float) -> None:
        """Record a metric value."""
        self.metrics[metric_name].append({
            "value": value,
            "timestamp": time.time()
        })
        
    def increment_counter(self, counter_name: str, amount: int = 1) -> None:
        """Increment a counter."""
        self.counters[counter_name] += amount
        
    def get_percentile(self, metric_name: str, percentile: float) -> Optional[float]:
        """Get percentile value for a metric."""
        values = [m["value"] for m in self.metrics.get(metric_name, [])]
        if not values:
            return None
            
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def get_average(self, metric_name: str) -> Optional[float]:
        """Get average value for a metric."""
        values = [m["value"] for m in self.metrics.get(metric_name, [])]
        if not values:
            return None
        return sum(values) / len(values)
    
    def get_rate(self, counter_name: str) -> float:
        """Get rate per second for a counter."""
        elapsed = time.time() - self.start_time
        if elapsed == 0:
            return 0
        return self.counters.get(counter_name, 0) / elapsed
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics."""
        summary = {
            "duration_seconds": time.time() - self.start_time,
            "counters": dict(self.counters),
            "rates": {},
            "metrics": {}
        }
        
        # Calculate rates
        for counter_name in self.counters:
            summary["rates"][f"{counter_name}_per_second"] = self.get_rate(counter_name)
        
        # Calculate metric statistics
        for metric_name in self.metrics:
            summary["metrics"][metric_name] = {
                "count": len(self.metrics[metric_name]),
                "average": self.get_average(metric_name),
                "p50": self.get_percentile(metric_name, 50),
                "p95": self.get_percentile(metric_name, 95),
                "p99": self.get_percentile(metric_name, 99),
                "min": min([m["value"] for m in self.metrics[metric_name]], default=None),
                "max": max([m["value"] for m in self.metrics[metric_name]], default=None)
            }
        
        return summary
    
    def reset(self) -> None:
        """Reset all metrics."""
        self.metrics.clear()
        self.counters.clear()
        self.start_time = time.time()


class SystemHealthMonitor:
    """Monitors system health during chaos experiments."""
    
    def __init__(self, check_interval: float = 1.0):
        self.check_interval = check_interval
        self.collector = MetricsCollector()
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._health_checks: List[Callable] = []
        
    async def start_monitoring(self) -> None:
        """Start continuous health monitoring."""
        if self._monitoring:
            return
            
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("System health monitoring started")
        
    async def stop_monitoring(self) -> None:
        """Stop health monitoring."""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("System health monitoring stopped")
        
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._monitoring:
            try:
                await self._collect_system_metrics()
                await self._run_health_checks()
                monitor_observations.add(1, {"type": "system_health"})
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                
    async def _collect_system_metrics(self) -> None:
        """Collect system-level metrics."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            self.collector.record_value("cpu_usage_percent", cpu_percent)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            self.collector.record_value("memory_usage_percent", memory.percent)
            self.collector.record_value("memory_available_mb", memory.available / (1024 * 1024))
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            self.collector.record_value("disk_usage_percent", disk.percent)
            
            # Network metrics (simplified)
            net_io = psutil.net_io_counters()
            self.collector.record_value("network_bytes_sent", net_io.bytes_sent)
            self.collector.record_value("network_bytes_recv", net_io.bytes_recv)
            
            # Process metrics
            process_count = len(psutil.pids())
            self.collector.record_value("process_count", process_count)
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            
    async def _run_health_checks(self) -> None:
        """Run registered health checks."""
        for check in self._health_checks:
            try:
                start_time = time.time()
                result = await check() if asyncio.iscoroutinefunction(check) else check()
                duration_ms = (time.time() - start_time) * 1000
                
                health_check_duration.record(duration_ms)
                
                if result:
                    self.collector.increment_counter("health_checks_passed")
                else:
                    self.collector.increment_counter("health_checks_failed")
                    
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                self.collector.increment_counter("health_checks_errors")
                
    def register_health_check(self, check: Callable) -> None:
        """Register a custom health check."""
        self._health_checks.append(check)
        
    async def get_metrics(self) -> Dict[str, Any]:
        """Get current health metrics."""
        summary = self.collector.get_summary()
        
        # Calculate derived metrics
        total_health_checks = (
            summary["counters"].get("health_checks_passed", 0) +
            summary["counters"].get("health_checks_failed", 0)
        )
        
        if total_health_checks > 0:
            success_rate = summary["counters"].get("health_checks_passed", 0) / total_health_checks
        else:
            success_rate = 1.0
            
        # Add current system state
        summary["current"] = {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
            "process_count": len(psutil.pids())
        }
        
        # Add health status
        summary["health"] = {
            "checks_total": total_health_checks,
            "checks_passed": summary["counters"].get("health_checks_passed", 0),
            "checks_failed": summary["counters"].get("health_checks_failed", 0),
            "success_rate": success_rate,
            "is_healthy": success_rate >= 0.9  # 90% threshold
        }
        
        # Add latency if available
        if "latency_ms" in summary["metrics"]:
            summary["latency_p99"] = summary["metrics"]["latency_ms"]["p99"]
        else:
            summary["latency_p99"] = 0
            
        # Add error rate
        total_requests = summary["counters"].get("requests_total", 0)
        failed_requests = summary["counters"].get("requests_failed", 0)
        
        if total_requests > 0:
            summary["error_rate"] = failed_requests / total_requests
        else:
            summary["error_rate"] = 0
            
        summary["success_rate"] = 1.0 - summary["error_rate"]
        
        return summary


class FaultMonitor:
    """Monitors active fault injections."""
    
    def __init__(self):
        self.active_faults: Dict[str, Dict[str, Any]] = {}
        self.fault_history: List[Dict[str, Any]] = []
        self.collector = MetricsCollector()
        
    async def monitor_fault(
        self,
        fault: FaultInjector,
        duration: int,
        interval: float = 1.0
    ) -> Dict[str, Any]:
        """Monitor a fault injection."""
        fault_id = f"{fault.config.type}_{int(time.time())}"
        
        self.active_faults[fault_id] = {
            "fault": fault,
            "start_time": datetime.now(),
            "metrics": MetricsCollector()
        }
        
        monitor_observations.add(1, {"type": "fault_start"})
        
        try:
            # Monitor for the duration
            elapsed = 0
            while elapsed < duration and fault.is_active:
                await self._collect_fault_metrics(fault_id)
                await asyncio.sleep(interval)
                elapsed += interval
                
        finally:
            # Record completion
            if fault_id in self.active_faults:
                fault_data = self.active_faults.pop(fault_id)
                fault_data["end_time"] = datetime.now()
                fault_data["duration"] = (fault_data["end_time"] - fault_data["start_time"]).total_seconds()
                fault_data["metrics_summary"] = fault_data["metrics"].get_summary()
                
                self.fault_history.append(fault_data)
                monitor_observations.add(1, {"type": "fault_end"})
                
        return self.get_fault_summary(fault_id)
        
    async def _collect_fault_metrics(self, fault_id: str) -> None:
        """Collect metrics for a specific fault."""
        if fault_id not in self.active_faults:
            return
            
        fault_data = self.active_faults[fault_id]
        metrics = fault_data["metrics"]
        
        # Collect fault-specific metrics
        fault = fault_data["fault"]
        
        if fault.config.type.startswith("network"):
            # Network fault metrics
            metrics.record_value("network_latency_impact", random.random() * 100)
            metrics.record_value("packet_loss_rate", random.random() * 10)
            
        elif fault.config.type.startswith("cpu"):
            # CPU fault metrics
            metrics.record_value("cpu_pressure", psutil.cpu_percent())
            
        elif fault.config.type.startswith("memory"):
            # Memory fault metrics
            metrics.record_value("memory_pressure", psutil.virtual_memory().percent)
            
    def get_fault_summary(self, fault_id: str) -> Dict[str, Any]:
        """Get summary for a specific fault."""
        # Check active faults
        if fault_id in self.active_faults:
            fault_data = self.active_faults[fault_id]
            return {
                "id": fault_id,
                "status": "active",
                "type": fault_data["fault"].config.type,
                "start_time": fault_data["start_time"].isoformat(),
                "metrics": fault_data["metrics"].get_summary()
            }
            
        # Check history
        for fault_data in self.fault_history:
            if fault_data.get("id") == fault_id:
                return {
                    "id": fault_id,
                    "status": "completed",
                    "type": fault_data["fault"].config.type,
                    "start_time": fault_data["start_time"].isoformat(),
                    "end_time": fault_data["end_time"].isoformat(),
                    "duration": fault_data["duration"],
                    "metrics": fault_data["metrics_summary"]
                }
                
        return {"id": fault_id, "status": "not_found"}
        
    def get_active_faults(self) -> List[Dict[str, Any]]:
        """Get list of active faults."""
        return [
            {
                "id": fault_id,
                "type": data["fault"].config.type,
                "name": data["fault"].config.name,
                "start_time": data["start_time"].isoformat(),
                "duration": (datetime.now() - data["start_time"]).total_seconds()
            }
            for fault_id, data in self.active_faults.items()
        ]
        
    def get_fault_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get fault injection history."""
        return [
            {
                "type": data["fault"].config.type,
                "name": data["fault"].config.name,
                "start_time": data["start_time"].isoformat(),
                "end_time": data["end_time"].isoformat(),
                "duration": data["duration"],
                "metrics": data.get("metrics_summary", {})
            }
            for data in self.fault_history[-limit:]
        ]


class RecoveryMonitor:
    """Monitors system recovery after fault injection."""
    
    def __init__(self, baseline_duration: int = 60):
        self.baseline_duration = baseline_duration
        self.baseline_metrics: Optional[Dict[str, Any]] = None
        self.recovery_metrics: List[Dict[str, Any]] = []
        
    async def establish_baseline(self, health_monitor: SystemHealthMonitor) -> None:
        """Establish baseline metrics before chaos."""
        logger.info(f"Establishing baseline for {self.baseline_duration}s...")
        
        # Collect metrics for baseline period
        start_time = time.time()
        baseline_collector = MetricsCollector()
        
        while time.time() - start_time < self.baseline_duration:
            metrics = await health_monitor.get_metrics()
            
            # Record key metrics
            baseline_collector.record_value("cpu_usage", metrics["current"]["cpu_percent"])
            baseline_collector.record_value("memory_usage", metrics["current"]["memory_percent"])
            baseline_collector.record_value("latency", metrics.get("latency_p99", 0))
            baseline_collector.record_value("error_rate", metrics.get("error_rate", 0))
            
            await asyncio.sleep(1)
            
        self.baseline_metrics = baseline_collector.get_summary()
        logger.info("Baseline established")
        
    async def monitor_recovery(
        self,
        health_monitor: SystemHealthMonitor,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """Monitor recovery after fault injection."""
        if not self.baseline_metrics:
            logger.warning("No baseline established, skipping recovery monitoring")
            return {"recovered": False, "reason": "no_baseline"}
            
        logger.info("Monitoring recovery...")
        start_time = time.time()
        recovery_collector = MetricsCollector()
        
        while time.time() - start_time < timeout:
            metrics = await health_monitor.get_metrics()
            
            # Check if recovered to baseline
            recovered = await self._check_recovery(metrics)
            
            if recovered:
                recovery_time = time.time() - start_time
                logger.info(f"System recovered in {recovery_time:.1f}s")
                
                return {
                    "recovered": True,
                    "recovery_time_seconds": recovery_time,
                    "metrics": recovery_collector.get_summary()
                }
                
            # Record recovery metrics
            recovery_collector.record_value("cpu_usage", metrics["current"]["cpu_percent"])
            recovery_collector.record_value("memory_usage", metrics["current"]["memory_percent"])
            recovery_collector.record_value("latency", metrics.get("latency_p99", 0))
            recovery_collector.record_value("error_rate", metrics.get("error_rate", 0))
            
            await asyncio.sleep(1)
            
        logger.warning(f"System did not recover within {timeout}s")
        return {
            "recovered": False,
            "reason": "timeout",
            "timeout_seconds": timeout,
            "metrics": recovery_collector.get_summary()
        }
        
    async def _check_recovery(self, current_metrics: Dict[str, Any]) -> bool:
        """Check if system has recovered to baseline."""
        if not self.baseline_metrics:
            return False
            
        # Define recovery thresholds (within 10% of baseline)
        threshold = 0.1
        
        baseline = self.baseline_metrics["metrics"]
        current = current_metrics["current"]
        
        # Check CPU
        if "cpu_usage" in baseline:
            baseline_cpu = baseline["cpu_usage"]["average"]
            if abs(current["cpu_percent"] - baseline_cpu) / max(baseline_cpu, 1) > threshold:
                return False
                
        # Check memory
        if "memory_usage" in baseline:
            baseline_memory = baseline["memory_usage"]["average"]
            if abs(current["memory_percent"] - baseline_memory) / max(baseline_memory, 1) > threshold:
                return False
                
        # Check error rate
        if current_metrics.get("error_rate", 0) > 0.01:  # 1% error threshold
            return False
            
        return True


# Import for random in monitoring simulations
import random