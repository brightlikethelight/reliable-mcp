"""Custom metrics for MCP reliability testing."""

import time
from typing import Dict, Any, Optional, List
from contextlib import contextmanager
import logging

try:
    from opentelemetry import metrics
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

from .telemetry import get_meter


class MCPMetrics:
    """Custom metrics collection for MCP operations."""
    
    def __init__(self, meter_name: str = "mcp-reliability-lab"):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.meter = get_meter(meter_name)
        
        if self.meter:
            self._init_instruments()
        else:
            self.logger.warning("Meter not available, metrics disabled")
    
    def _init_instruments(self):
        """Initialize OpenTelemetry instruments."""
        # Counters
        self.tool_calls_total = self.meter.create_counter(
            "mcp_tool_calls_total",
            description="Total number of tool calls made",
            unit="1"
        )
        
        self.tool_call_errors_total = self.meter.create_counter(
            "mcp_tool_call_errors_total", 
            description="Total number of tool call errors",
            unit="1"
        )
        
        self.connection_attempts_total = self.meter.create_counter(
            "mcp_connection_attempts_total",
            description="Total number of connection attempts",
            unit="1"
        )
        
        self.retry_attempts_total = self.meter.create_counter(
            "mcp_retry_attempts_total",
            description="Total number of retry attempts",
            unit="1"
        )
        
        # Histograms
        self.tool_call_duration = self.meter.create_histogram(
            "mcp_tool_call_duration_seconds",
            description="Duration of tool calls",
            unit="s"
        )
        
        self.connection_duration = self.meter.create_histogram(
            "mcp_connection_duration_seconds",
            description="Duration of connection establishment",
            unit="s"
        )
        
        self.payload_size = self.meter.create_histogram(
            "mcp_payload_size_bytes",
            description="Size of MCP message payloads",
            unit="bytes"
        )
        
        # Gauges (using UpDownCounter)
        self.active_connections = self.meter.create_up_down_counter(
            "mcp_active_connections",
            description="Number of active MCP connections",
            unit="1"
        )
        
        self.circuit_breaker_state = self.meter.create_up_down_counter(
            "mcp_circuit_breaker_state",
            description="Circuit breaker state (0=closed, 1=half-open, 2=open)",
            unit="1"
        )
    
    def record_tool_call(
        self, 
        tool_name: str, 
        duration: float,
        status: str = "success",
        transport: str = "stdio",
        server_type: str = "python"
    ) -> None:
        """Record a tool call with metrics."""
        if not self.meter:
            return
            
        attributes = {
            "tool_name": tool_name,
            "status": status,
            "transport": transport,
            "server_type": server_type
        }
        
        self.tool_calls_total.add(1, attributes)
        self.tool_call_duration.record(duration, attributes)
        
        if status == "error":
            self.tool_call_errors_total.add(1, attributes)
    
    def record_connection_attempt(
        self,
        transport: str,
        success: bool,
        duration: float,
        error_type: Optional[str] = None
    ) -> None:
        """Record a connection attempt."""
        if not self.meter:
            return
            
        attributes = {
            "transport": transport,
            "success": success
        }
        
        if error_type:
            attributes["error_type"] = error_type
            
        self.connection_attempts_total.add(1, attributes)
        self.connection_duration.record(duration, attributes)
    
    def record_retry_attempt(
        self,
        operation: str,
        attempt: int,
        max_attempts: int,
        error_type: str
    ) -> None:
        """Record a retry attempt."""
        if not self.meter:
            return
            
        self.retry_attempts_total.add(1, {
            "operation": operation,
            "attempt": attempt,
            "max_attempts": max_attempts,
            "error_type": error_type
        })
    
    def record_payload_size(
        self,
        size: int,
        direction: str,  # "inbound" or "outbound"
        message_type: str
    ) -> None:
        """Record payload size."""
        if not self.meter:
            return
            
        self.payload_size.record(size, {
            "direction": direction,
            "message_type": message_type
        })
    
    def set_active_connections(self, count: int, transport: str) -> None:
        """Set the number of active connections."""
        if not self.meter:
            return
            
        # This is a simplified approach - in reality, we'd want to track deltas
        self.active_connections.add(count, {"transport": transport})
    
    def set_circuit_breaker_state(
        self,
        state: str,  # "closed", "half_open", "open"
        operation: str
    ) -> None:
        """Set circuit breaker state."""
        if not self.meter:
            return
            
        state_value = {"closed": 0, "half_open": 1, "open": 2}.get(state, 0)
        self.circuit_breaker_state.add(state_value, {"operation": operation})
    
    @contextmanager
    def time_operation(self, operation_name: str, **attributes):
        """Context manager for timing operations."""
        start_time = time.time()
        try:
            yield
            duration = time.time() - start_time
            if operation_name == "tool_call":
                self.record_tool_call(
                    attributes.get("tool_name", "unknown"),
                    duration,
                    "success",
                    attributes.get("transport", "stdio"),
                    attributes.get("server_type", "python")
                )
        except Exception as e:
            duration = time.time() - start_time
            if operation_name == "tool_call":
                self.record_tool_call(
                    attributes.get("tool_name", "unknown"),
                    duration,
                    "error",
                    attributes.get("transport", "stdio"),
                    attributes.get("server_type", "python")
                )
            raise


class PropertyTestingMetrics:
    """Specialized metrics for property-based testing."""
    
    def __init__(self, meter_name: str = "mcp-property-testing"):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.meter = get_meter(meter_name)
        
        if self.meter:
            self._init_instruments()
    
    def _init_instruments(self):
        """Initialize property testing instruments."""
        self.hypothesis_examples_total = self.meter.create_counter(
            "hypothesis_examples_total",
            description="Total number of Hypothesis examples generated",
            unit="1"
        )
        
        self.hypothesis_failures_total = self.meter.create_counter(
            "hypothesis_failures_total",
            description="Total number of Hypothesis test failures",
            unit="1"
        )
        
        self.hypothesis_shrinks_total = self.meter.create_counter(
            "hypothesis_shrinks_total",
            description="Total number of Hypothesis shrinking attempts",
            unit="1"
        )
        
        self.property_test_duration = self.meter.create_histogram(
            "property_test_duration_seconds",
            description="Duration of property test runs",
            unit="s"
        )
    
    def record_hypothesis_run(
        self,
        test_name: str,
        examples_count: int,
        failures_count: int,
        shrinks_count: int,
        duration: float
    ) -> None:
        """Record Hypothesis test run metrics."""
        if not self.meter:
            return
            
        attributes = {"test_name": test_name}
        
        self.hypothesis_examples_total.add(examples_count, attributes)
        self.hypothesis_failures_total.add(failures_count, attributes)
        self.hypothesis_shrinks_total.add(shrinks_count, attributes)
        self.property_test_duration.record(duration, attributes)


class ChaosEngineeringMetrics:
    """Specialized metrics for chaos engineering."""
    
    def __init__(self, meter_name: str = "mcp-chaos-engineering"):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.meter = get_meter(meter_name)
        
        if self.meter:
            self._init_instruments()
    
    def _init_instruments(self):
        """Initialize chaos engineering instruments."""
        self.chaos_experiments_total = self.meter.create_counter(
            "chaos_experiments_total",
            description="Total number of chaos experiments executed",
            unit="1"
        )
        
        self.chaos_faults_injected_total = self.meter.create_counter(
            "chaos_faults_injected_total",
            description="Total number of faults injected",
            unit="1"
        )
        
        self.chaos_recovery_time = self.meter.create_histogram(
            "chaos_recovery_time_seconds",
            description="Time taken to recover from chaos faults",
            unit="s"
        )
        
        self.system_resilience_score = self.meter.create_histogram(
            "system_resilience_score",
            description="System resilience score (0-100)",
            unit="1"
        )
    
    def record_chaos_experiment(
        self,
        experiment_name: str,
        fault_type: str,
        success_rate: float,
        recovery_time: Optional[float] = None
    ) -> None:
        """Record chaos experiment results."""
        if not self.meter:
            return
            
        attributes = {
            "experiment_name": experiment_name,
            "fault_type": fault_type
        }
        
        self.chaos_experiments_total.add(1, attributes)
        self.chaos_faults_injected_total.add(1, attributes)
        
        if recovery_time is not None:
            self.chaos_recovery_time.record(recovery_time, attributes)
            
        # Convert success rate to resilience score
        resilience_score = success_rate * 100
        self.system_resilience_score.record(resilience_score, attributes)