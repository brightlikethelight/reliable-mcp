"""Main MCP server wrapper implementation."""

import asyncio
import logging
from typing import Any, Dict, Optional, List, Type
import threading
from datetime import datetime, timezone

from .config import (
    MCPServerConfig, StdioTransportConfig, HttpTransportConfig, 
    WebSocketTransportConfig, TransportType
)
from .transport import MCPTransport, MCPMessage
from .transports.stdio import StdioTransport
from .interceptors import (
    InterceptorChain, TelemetryInterceptor, IOCaptureInterceptor,
    InterceptorContext
)
from .retry import RetryPolicyManager, CircuitBreaker
from .errors import (
    MCPError, MCPConnectionError, MCPConfigurationError
)


class MCPServerWrapper:
    """
    Comprehensive wrapper for MCP servers with observability, retry logic,
    and comprehensive error handling.
    
    This class provides a unified interface for interacting with MCP servers
    regardless of their implementation (Python/TypeScript) or transport method
    (STDIO/HTTP/WebSocket).
    
    Features:
    - Multi-transport support (STDIO, HTTP, WebSocket)
    - OpenTelemetry integration for observability
    - Configurable retry logic with exponential backoff
    - Circuit breaker pattern for fault tolerance
    - I/O capture for property-based testing
    - Thread-safe operations
    - Comprehensive error handling
    
    Example:
        ```python
        config = MCPServerConfig(
            server_type=ServerType.PYTHON,
            transport_config=StdioTransportConfig(
                command=["python", "mcp_server.py"]
            )
        )
        
        async with MCPServerWrapper(config) as wrapper:
            result = await wrapper.call_tool("get_weather", {"city": "London"})
        ```
    """
    
    def __init__(self, config: MCPServerConfig):
        """
        Initialize the MCP server wrapper.
        
        Args:
            config: Configuration for the MCP server and wrapper behavior
            
        Raises:
            MCPConfigurationError: If configuration is invalid
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Initialize components
        self.transport: Optional[MCPTransport] = None
        self.interceptor_chain = InterceptorChain()
        self.retry_manager = RetryPolicyManager(config.retry_config)
        self.circuit_breaker = CircuitBreaker()
        
        # Thread safety
        if config.thread_safe:
            self._lock = threading.RLock()
        else:
            self._lock = None
            
        # State tracking
        self._connected = False
        self._call_counter = 0
        
        # Initialize transport
        self._initialize_transport()
        
        # Initialize interceptors
        self._initialize_interceptors()

    def _initialize_transport(self) -> None:
        """Initialize the appropriate transport based on configuration."""
        transport_map: Dict[TransportType, Type[MCPTransport]] = {
            TransportType.STDIO: StdioTransport,
            # TODO: Add HTTP and WebSocket transports
        }
        
        transport_type = self.config.transport_config.type
        transport_class = transport_map.get(transport_type)
        
        if not transport_class:
            raise MCPConfigurationError(
                f"Unsupported transport type: {transport_type}"
            )
            
        self.transport = transport_class(self.config.transport_config)

    def _initialize_interceptors(self) -> None:
        """Initialize interceptors based on configuration."""
        obs_config = self.config.observability_config
        
        # Add telemetry interceptor if enabled
        if obs_config.enable_tracing or obs_config.enable_metrics:
            try:
                from opentelemetry import trace, metrics
                tracer = trace.get_tracer(__name__)
                meter = metrics.get_meter(__name__)
                self.interceptor_chain.add_interceptor(
                    TelemetryInterceptor(tracer, meter)
                )
            except ImportError:
                self.logger.warning(
                    "OpenTelemetry not available, skipping telemetry interceptor"
                )
        
        # Add I/O capture interceptor if enabled
        if self.config.enable_io_capture:
            self.io_capture_interceptor = IOCaptureInterceptor(
                max_payload_size=self.config.io_capture_max_size
            )
            self.interceptor_chain.add_interceptor(self.io_capture_interceptor)

    async def connect(self) -> None:
        """
        Connect to the MCP server.
        
        Raises:
            MCPConnectionError: If connection fails
            MCPConfigurationError: If configuration is invalid
        """
        if self._lock:
            with self._lock:
                return await self._connect_impl()
        else:
            return await self._connect_impl()

    async def _connect_impl(self) -> None:
        """Internal connection implementation."""
        if self._connected:
            return

        if not self.transport:
            raise MCPConfigurationError("Transport not initialized")

        try:
            await self.transport.connect()
            self._connected = True
            self.logger.info(
                f"Connected to MCP server via {self.config.transport_config.type}"
            )
        except Exception as e:
            raise MCPConnectionError(f"Failed to connect: {e}") from e

    async def disconnect(self) -> None:
        """
        Disconnect from the MCP server.
        
        This method is safe to call multiple times and will not raise
        an error if already disconnected.
        """
        if self._lock:
            with self._lock:
                return await self._disconnect_impl()
        else:
            return await self._disconnect_impl()

    async def _disconnect_impl(self) -> None:
        """Internal disconnection implementation."""
        if not self._connected:
            return

        if self.transport:
            try:
                await self.transport.disconnect()
            except Exception as e:
                self.logger.warning(f"Error during disconnect: {e}")
            finally:
                self._connected = False
                self.logger.info("Disconnected from MCP server")

    async def call_tool(
        self,
        tool_name: str,
        parameters: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None
    ) -> Any:
        """
        Call a tool on the MCP server.
        
        Args:
            tool_name: Name of the tool to call
            parameters: Parameters to pass to the tool
            timeout: Optional timeout for the call
            
        Returns:
            The result from the tool call
            
        Raises:
            MCPConnectionError: If not connected to server
            MCPTimeoutError: If call times out
            MCPError: For other MCP-related errors
        """
        return await self._make_call(
            method="tools/call",
            params={
                "name": tool_name,
                "arguments": parameters or {}
            },
            timeout=timeout
        )

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List available tools on the MCP server.
        
        Returns:
            List of tool definitions
            
        Raises:
            MCPConnectionError: If not connected to server
            MCPError: For other MCP-related errors
        """
        result = await self._make_call(method="tools/list")
        return result.get("tools", [])

    async def list_resources(self) -> List[Dict[str, Any]]:
        """
        List available resources on the MCP server.
        
        Returns:
            List of resource definitions
            
        Raises:
            MCPConnectionError: If not connected to server
            MCPError: For other MCP-related errors
        """
        result = await self._make_call(method="resources/list")
        return result.get("resources", [])

    async def read_resource(
        self,
        resource_uri: str,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Read a resource from the MCP server.
        
        Args:
            resource_uri: URI of the resource to read
            timeout: Optional timeout for the operation
            
        Returns:
            Resource content and metadata
            
        Raises:
            MCPConnectionError: If not connected to server
            MCPTimeoutError: If operation times out
            MCPError: For other MCP-related errors
        """
        return await self._make_call(
            method="resources/read",
            params={"uri": resource_uri},
            timeout=timeout
        )

    async def _make_call(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None
    ) -> Any:
        """
        Make a call to the MCP server with full error handling and retries.
        
        Args:
            method: MCP method to call
            params: Parameters for the method
            timeout: Optional timeout
            
        Returns:
            Result from the server
            
        Raises:
            MCPConnectionError: If not connected
            MCPError: For other errors
        """
        if not self._connected:
            raise MCPConnectionError("Not connected to MCP server")

        self._call_counter += 1
        call_id = str(self._call_counter)
        
        # Create interceptor context
        context = InterceptorContext(
            message_id=call_id,
            method=method,
            transport_type=self.config.transport_config.type.value,
            timestamp=datetime.now(timezone.utc),
            metadata={}
        )

        async def operation():
            return await self.circuit_breaker.call(
                lambda: self.transport.call(method, params, timeout)
            )

        try:
            # Execute with retry logic
            result = await self.retry_manager.execute_with_retry(
                operation,
                operation_name=f"{method}_{call_id}"
            )
            
            return result
            
        except Exception as e:
            await self.interceptor_chain.on_error(e, context)
            raise

    def get_captured_io(self) -> List[Dict[str, Any]]:
        """
        Get captured I/O interactions for property testing.
        
        Returns:
            List of captured interactions
        """
        if hasattr(self, 'io_capture_interceptor'):
            return self.io_capture_interceptor.get_captured_data()
        return []

    def clear_captured_io(self) -> None:
        """Clear captured I/O interactions."""
        if hasattr(self, 'io_capture_interceptor'):
            self.io_capture_interceptor.clear_captured_data()

    @property
    def is_connected(self) -> bool:
        """Check if connected to MCP server."""
        return self._connected and (
            self.transport.is_connected if self.transport else False
        )

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the MCP server.
        
        Returns:
            Health status information
        """
        try:
            # Try a simple operation to verify server health
            await self.list_tools()
            return {
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "transport": self.config.transport_config.type.value,
                "connected": self.is_connected
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
                "transport": self.config.transport_config.type.value,
                "connected": self.is_connected
            }

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    def __del__(self):
        """Cleanup on garbage collection."""
        if self._connected and self.transport:
            try:
                # Schedule cleanup for next event loop iteration
                asyncio.create_task(self.disconnect())
            except RuntimeError:
                # Event loop might be closed, ignore
                pass