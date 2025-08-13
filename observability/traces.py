"""Custom tracing utilities for MCP reliability testing."""

from typing import Dict, Any, Optional, Union
from contextlib import contextmanager
import logging
import json

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

from .telemetry import get_tracer


class MCPTracer:
    """Custom tracer for MCP operations with enhanced context."""
    
    def __init__(self, tracer_name: str = "mcp-reliability-lab"):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.tracer = get_tracer(tracer_name)
    
    @contextmanager
    def trace_tool_call(
        self,
        tool_name: str,
        parameters: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        transport_type: str = "stdio",
        server_type: str = "python"
    ):
        """Trace a tool call with comprehensive context."""
        if not self.tracer:
            yield None
            return
            
        with self.tracer.start_as_current_span(
            f"mcp.tool_call.{tool_name}",
            attributes={
                "mcp.operation": "tool_call",
                "mcp.tool.name": tool_name,
                "mcp.transport.type": transport_type,
                "mcp.server.type": server_type,
                "mcp.timeout": timeout or 0,
                "mcp.has_parameters": parameters is not None,
                "mcp.parameter_count": len(parameters) if parameters else 0
            }
        ) as span:
            try:
                # Add parameter details if available and not too large
                if parameters and len(str(parameters)) < 1000:
                    span.set_attribute("mcp.parameters", json.dumps(parameters))
                
                yield span
                
                # Mark as successful if no exception
                span.set_status(Status(StatusCode.OK))
                
            except Exception as e:
                span.record_exception(e)
                span.set_status(
                    Status(StatusCode.ERROR, description=str(e))
                )
                span.set_attribute("mcp.error.type", type(e).__name__)
                span.set_attribute("mcp.error.message", str(e))
                raise
    
    @contextmanager
    def trace_connection(
        self,
        transport_type: str,
        server_type: str,
        connection_config: Optional[Dict[str, Any]] = None
    ):
        """Trace connection establishment."""
        if not self.tracer:
            yield None
            return
            
        with self.tracer.start_as_current_span(
            f"mcp.connection.{transport_type}",
            attributes={
                "mcp.operation": "connection",
                "mcp.transport.type": transport_type,
                "mcp.server.type": server_type
            }
        ) as span:
            try:
                # Add safe connection config details
                if connection_config:
                    safe_config = self._sanitize_config(connection_config)
                    for key, value in safe_config.items():
                        span.set_attribute(f"mcp.config.{key}", value)
                
                yield span
                span.set_status(Status(StatusCode.OK))
                
            except Exception as e:
                span.record_exception(e)
                span.set_status(
                    Status(StatusCode.ERROR, description=str(e))
                )
                span.set_attribute("mcp.error.type", type(e).__name__)
                raise
    
    @contextmanager
    def trace_retry_operation(
        self,
        operation_name: str,
        attempt: int,
        max_attempts: int
    ):
        """Trace retry attempts."""
        if not self.tracer:
            yield None
            return
            
        with self.tracer.start_as_current_span(
            f"mcp.retry.{operation_name}",
            attributes={
                "mcp.operation": "retry",
                "mcp.retry.operation_name": operation_name,
                "mcp.retry.attempt": attempt,
                "mcp.retry.max_attempts": max_attempts,
                "mcp.retry.is_final_attempt": attempt == max_attempts
            }
        ) as span:
            try:
                yield span
                span.set_status(Status(StatusCode.OK))
                
            except Exception as e:
                span.record_exception(e)
                span.set_status(
                    Status(StatusCode.ERROR, description=str(e))
                )
                span.set_attribute("mcp.retry.failed", True)
                span.set_attribute("mcp.error.type", type(e).__name__)
                raise
    
    @contextmanager
    def trace_message_processing(
        self,
        message_type: str,
        direction: str,  # "inbound" or "outbound"
        message_id: Optional[str] = None,
        payload_size: Optional[int] = None
    ):
        """Trace message processing."""
        if not self.tracer:
            yield None
            return
            
        with self.tracer.start_as_current_span(
            f"mcp.message.{direction}",
            attributes={
                "mcp.operation": "message_processing",
                "mcp.message.type": message_type,
                "mcp.message.direction": direction,
                "mcp.message.id": message_id or "unknown",
                "mcp.message.payload_size": payload_size or 0
            }
        ) as span:
            try:
                yield span
                span.set_status(Status(StatusCode.OK))
                
            except Exception as e:
                span.record_exception(e)
                span.set_status(
                    Status(StatusCode.ERROR, description=str(e))
                )
                raise
    
    @contextmanager
    def trace_property_test(
        self,
        test_name: str,
        example_count: Optional[int] = None,
        strategy: Optional[str] = None
    ):
        """Trace property-based testing."""
        if not self.tracer:
            yield None
            return
            
        with self.tracer.start_as_current_span(
            f"mcp.property_test.{test_name}",
            attributes={
                "mcp.operation": "property_test",
                "mcp.test.name": test_name,
                "mcp.test.type": "property_based",
                "mcp.test.example_count": example_count or 0,
                "mcp.test.strategy": strategy or "unknown"
            }
        ) as span:
            try:
                yield span
                span.set_status(Status(StatusCode.OK))
                
            except Exception as e:
                span.record_exception(e)
                span.set_status(
                    Status(StatusCode.ERROR, description=str(e))
                )
                span.set_attribute("mcp.test.failed", True)
                span.set_attribute("mcp.error.type", type(e).__name__)
                raise
    
    @contextmanager
    def trace_chaos_experiment(
        self,
        experiment_name: str,
        fault_type: str,
        fault_config: Optional[Dict[str, Any]] = None
    ):
        """Trace chaos engineering experiments."""
        if not self.tracer:
            yield None
            return
            
        with self.tracer.start_as_current_span(
            f"mcp.chaos.{experiment_name}",
            attributes={
                "mcp.operation": "chaos_experiment",
                "mcp.chaos.experiment_name": experiment_name,
                "mcp.chaos.fault_type": fault_type
            }
        ) as span:
            try:
                # Add fault configuration details
                if fault_config:
                    for key, value in fault_config.items():
                        if isinstance(value, (str, int, float, bool)):
                            span.set_attribute(f"mcp.chaos.config.{key}", value)
                
                yield span
                span.set_status(Status(StatusCode.OK))
                
            except Exception as e:
                span.record_exception(e)
                span.set_status(
                    Status(StatusCode.ERROR, description=str(e))
                )
                span.set_attribute("mcp.chaos.failed", True)
                raise
    
    def add_event(
        self,
        span: Optional[trace.Span],
        event_name: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add an event to a span."""
        if span and self.tracer:
            span.add_event(event_name, attributes or {})
    
    def set_attribute(
        self,
        span: Optional[trace.Span],
        key: str,
        value: Union[str, int, float, bool]
    ) -> None:
        """Set an attribute on a span."""
        if span and self.tracer:
            span.set_attribute(key, value)
    
    def _sanitize_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from configuration."""
        sanitized = {}
        sensitive_keys = {
            'password', 'token', 'key', 'secret', 'auth', 'credential'
        }
        
        for key, value in config.items():
            lower_key = key.lower()
            if any(sensitive in lower_key for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            else:
                sanitized[key] = str(type(value).__name__)
        
        return sanitized


class DistributedTraceContext:
    """Manages distributed tracing context across MCP operations."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.tracer = get_tracer("mcp-distributed-context")
    
    def inject_context(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Inject tracing context into headers."""
        if not self.tracer or not OTEL_AVAILABLE:
            return headers
            
        try:
            from opentelemetry.propagate import inject
            inject(headers)
            return headers
        except Exception as e:
            self.logger.warning(f"Failed to inject trace context: {e}")
            return headers
    
    def extract_context(self, headers: Dict[str, str]) -> None:
        """Extract tracing context from headers."""
        if not self.tracer or not OTEL_AVAILABLE:
            return
            
        try:
            from opentelemetry.propagate import extract
            from opentelemetry.context import attach
            context = extract(headers)
            attach(context)
        except Exception as e:
            self.logger.warning(f"Failed to extract trace context: {e}")
    
    def create_child_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> Optional[trace.Span]:
        """Create a child span from current context."""
        if not self.tracer:
            return None
            
        try:
            span = self.tracer.start_span(name, attributes=attributes or {})
            return span
        except Exception as e:
            self.logger.warning(f"Failed to create child span: {e}")
            return None