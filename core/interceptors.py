"""Message interceptor system for MCP reliability testing."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import uuid
import logging

from .transport import MCPMessage
from .errors import MCPError


@dataclass
class InterceptorContext:
    """Context information for message interception."""
    message_id: str
    method: str
    transport_type: str
    timestamp: datetime
    metadata: Dict[str, Any]


class MCPInterceptor(ABC):
    """Abstract base class for message interceptors."""
    
    @abstractmethod
    async def before_send(
        self, 
        message: MCPMessage, 
        context: InterceptorContext
    ) -> MCPMessage:
        """Called before sending a message."""
        pass

    @abstractmethod
    async def after_receive(
        self, 
        message: MCPMessage, 
        context: InterceptorContext
    ) -> MCPMessage:
        """Called after receiving a message."""
        pass

    @abstractmethod
    async def on_error(
        self, 
        error: Exception, 
        context: InterceptorContext
    ) -> None:
        """Called when an error occurs."""
        pass


class TelemetryInterceptor(MCPInterceptor):
    """Interceptor for OpenTelemetry integration."""
    
    def __init__(self, tracer, meter):
        self.tracer = tracer
        self.meter = meter
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Create metrics
        self.call_counter = meter.create_counter(
            "mcp_calls_total",
            description="Total number of MCP calls"
        )
        self.call_duration = meter.create_histogram(
            "mcp_call_duration_seconds",
            description="Duration of MCP calls"
        )
        self.error_counter = meter.create_counter(
            "mcp_errors_total", 
            description="Total number of MCP errors"
        )

    async def before_send(
        self, 
        message: MCPMessage, 
        context: InterceptorContext
    ) -> MCPMessage:
        """Start tracing span and record metrics."""
        try:
            span = self.tracer.start_span(
                f"mcp_call_{message.method}",
                attributes={
                    "mcp.method": message.method,
                    "mcp.message_id": message.id,
                    "mcp.transport": context.transport_type
                }
            )
            
            context.metadata["span"] = span
            context.metadata["start_time"] = datetime.now(timezone.utc)
            
            self.call_counter.add(1, {
                "method": message.method,
                "transport": context.transport_type
            })
        except Exception as e:
            self.logger.warning(f"Error in telemetry before_send: {e}")
        
        return message

    async def after_receive(
        self, 
        message: MCPMessage, 
        context: InterceptorContext
    ) -> MCPMessage:
        """End tracing span and record duration."""
        try:
            span = context.metadata.get("span")
            start_time = context.metadata.get("start_time")
            
            if span:
                if message.error:
                    span.set_status(description=str(message.error))
                span.end()
                
            if start_time:
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                self.call_duration.record(duration, {
                    "method": context.method,
                    "transport": context.transport_type,
                    "status": "error" if message.error else "success"
                })
        except Exception as e:
            self.logger.warning(f"Error in telemetry after_receive: {e}")
            
        return message

    async def on_error(
        self, 
        error: Exception, 
        context: InterceptorContext
    ) -> None:
        """Record error metrics and update span."""
        try:
            self.error_counter.add(1, {
                "method": context.method,
                "transport": context.transport_type,
                "error_type": type(error).__name__
            })
            
            span = context.metadata.get("span")
            if span:
                span.record_exception(error)
                span.set_status(description=str(error))
                span.end()
        except Exception as e:
            self.logger.warning(f"Error in telemetry on_error: {e}")


class IOCaptureInterceptor(MCPInterceptor):
    """Interceptor for capturing I/O for property testing."""
    
    def __init__(self, max_payload_size: int = 10240):
        self.max_payload_size = max_payload_size
        self.captured_interactions: List[Dict[str, Any]] = []
        self.logger = logging.getLogger(self.__class__.__name__)

    async def before_send(
        self, 
        message: MCPMessage, 
        context: InterceptorContext
    ) -> MCPMessage:
        """Capture outgoing message."""
        try:
            payload = message.to_json()
            if len(payload) <= self.max_payload_size:
                interaction = {
                    "id": str(uuid.uuid4()),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "direction": "outgoing",
                    "method": message.method,
                    "message_id": message.id,
                    "payload": payload,
                    "context": {
                        "transport": context.transport_type,
                        "metadata": context.metadata.copy()
                    }
                }
                self.captured_interactions.append(interaction)
                context.metadata["capture_id"] = interaction["id"]
        except Exception as e:
            self.logger.warning(f"Error capturing outgoing message: {e}")
            
        return message

    async def after_receive(
        self, 
        message: MCPMessage, 
        context: InterceptorContext
    ) -> MCPMessage:
        """Capture incoming message."""
        try:
            payload = message.to_json()
            if len(payload) <= self.max_payload_size:
                interaction = {
                    "id": str(uuid.uuid4()),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "direction": "incoming",
                    "method": context.method,
                    "message_id": message.id,
                    "payload": payload,
                    "context": {
                        "transport": context.transport_type,
                        "related_capture_id": context.metadata.get("capture_id"),
                        "metadata": context.metadata.copy()
                    }
                }
                self.captured_interactions.append(interaction)
        except Exception as e:
            self.logger.warning(f"Error capturing incoming message: {e}")
            
        return message

    async def on_error(
        self, 
        error: Exception, 
        context: InterceptorContext
    ) -> None:
        """Capture error information."""
        try:
            interaction = {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "direction": "error",
                "method": context.method,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": {
                    "transport": context.transport_type,
                    "related_capture_id": context.metadata.get("capture_id"),
                    "metadata": context.metadata.copy()
                }
            }
            self.captured_interactions.append(interaction)
        except Exception as e:
            self.logger.warning(f"Error capturing error: {e}")

    def get_captured_data(self) -> List[Dict[str, Any]]:
        """Get all captured interactions."""
        return self.captured_interactions.copy()

    def clear_captured_data(self) -> None:
        """Clear captured interactions."""
        self.captured_interactions.clear()


class InterceptorChain:
    """Manages a chain of interceptors."""
    
    def __init__(self):
        self.interceptors: List[MCPInterceptor] = []
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_interceptor(self, interceptor: MCPInterceptor) -> None:
        """Add an interceptor to the chain."""
        self.interceptors.append(interceptor)

    async def before_send(
        self, 
        message: MCPMessage, 
        context: InterceptorContext
    ) -> MCPMessage:
        """Apply all before_send interceptors."""
        current_message = message
        for interceptor in self.interceptors:
            current_message = await interceptor.before_send(current_message, context)
        return current_message

    async def after_receive(
        self, 
        message: MCPMessage, 
        context: InterceptorContext
    ) -> MCPMessage:
        """Apply all after_receive interceptors."""
        current_message = message
        for interceptor in reversed(self.interceptors):
            current_message = await interceptor.after_receive(current_message, context)
        return current_message

    async def on_error(
        self, 
        error: Exception, 
        context: InterceptorContext
    ) -> None:
        """Notify all interceptors of error."""
        for interceptor in self.interceptors:
            try:
                await interceptor.on_error(error, context)
            except Exception as e:
                self.logger.warning(
                    f"Interceptor {interceptor.__class__.__name__} failed: {e}"
                )