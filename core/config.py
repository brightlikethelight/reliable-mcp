"""Configuration models for MCP reliability testing framework."""

from enum import Enum
from typing import Dict, Any, Optional, Union, List
from pydantic import BaseModel, Field, validator


class TransportType(str, Enum):
    """Supported transport types for MCP communication."""
    STDIO = "stdio"
    HTTP = "http"
    WEBSOCKET = "websocket"


class ServerType(str, Enum):
    """Supported MCP server implementations."""
    PYTHON = "python"
    TYPESCRIPT = "typescript"


class RetryStrategy(str, Enum):
    """Available retry strategies."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"


class MCPRetryConfig(BaseModel):
    """Configuration for retry behavior."""
    max_attempts: int = Field(default=3, ge=1, le=10)
    initial_delay: float = Field(default=1.0, ge=0.1)
    max_delay: float = Field(default=60.0, ge=1.0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0)
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    retry_on_errors: List[str] = Field(
        default_factory=lambda: [
            "timeout", "connection_error", "server_error", "internal_error"
        ]
    )


class MCPTimeoutConfig(BaseModel):
    """Configuration for timeout behavior."""
    connection_timeout: float = Field(default=30.0, ge=1.0)
    read_timeout: float = Field(default=60.0, ge=1.0)
    write_timeout: float = Field(default=30.0, ge=1.0)
    call_timeout: float = Field(default=300.0, ge=1.0)


class MCPObservabilityConfig(BaseModel):
    """Configuration for observability features."""
    enable_tracing: bool = True
    enable_metrics: bool = True
    enable_logging: bool = True
    trace_sampling_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    log_level: str = "INFO"
    capture_payloads: bool = True
    max_payload_size: int = Field(default=10240, ge=1024)  # 10KB default


class MCPTransportConfig(BaseModel):
    """Base transport configuration."""
    type: TransportType
    timeout_config: MCPTimeoutConfig = Field(default_factory=MCPTimeoutConfig)


class StdioTransportConfig(MCPTransportConfig):
    """Configuration for STDIO transport."""
    type: TransportType = TransportType.STDIO
    command: List[str]
    working_directory: Optional[str] = None
    environment_variables: Dict[str, str] = Field(default_factory=dict)
    buffer_size: int = Field(default=8192, ge=1024)


class HttpTransportConfig(MCPTransportConfig):
    """Configuration for HTTP transport."""
    type: TransportType = TransportType.HTTP
    base_url: str
    headers: Dict[str, str] = Field(default_factory=dict)
    max_connections: int = Field(default=10, ge=1)
    keep_alive: bool = True
    verify_ssl: bool = True


class WebSocketTransportConfig(MCPTransportConfig):
    """Configuration for WebSocket transport."""
    type: TransportType = TransportType.WEBSOCKET
    url: str
    headers: Dict[str, str] = Field(default_factory=dict)
    ping_interval: float = Field(default=30.0, ge=1.0)
    ping_timeout: float = Field(default=10.0, ge=1.0)
    max_message_size: int = Field(default=1048576, ge=1024)  # 1MB default


class MCPServerConfig(BaseModel):
    """Main configuration for MCP server wrapper."""
    server_type: ServerType
    transport_config: Union[
        StdioTransportConfig, 
        HttpTransportConfig, 
        WebSocketTransportConfig
    ]
    retry_config: MCPRetryConfig = Field(default_factory=MCPRetryConfig)
    observability_config: MCPObservabilityConfig = Field(
        default_factory=MCPObservabilityConfig
    )
    enable_io_capture: bool = True
    io_capture_max_size: int = Field(default=1048576, ge=1024)  # 1MB
    thread_safe: bool = True

    class Config:
        use_enum_values = True