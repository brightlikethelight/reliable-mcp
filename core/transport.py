"""Transport abstraction layer for MCP communication."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union
import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from .config import MCPTransportConfig
from .errors import MCPTransportError, MCPTimeoutError


@dataclass
class MCPMessage:
    """Represents an MCP message."""
    id: Optional[str]
    method: Optional[str] 
    params: Optional[Dict[str, Any]]
    result: Optional[Any]
    error: Optional[Dict[str, Any]]
    timestamp: datetime
    raw_data: bytes
    
    @classmethod
    def from_json(cls, data: Union[str, bytes]) -> 'MCPMessage':
        """Create MCPMessage from JSON data."""
        if isinstance(data, bytes):
            raw_data = data
            data = data.decode('utf-8')
        else:
            raw_data = data.encode('utf-8')
            
        try:
            parsed = json.loads(data)
            return cls(
                id=parsed.get('id'),
                method=parsed.get('method'),
                params=parsed.get('params'),
                result=parsed.get('result'),
                error=parsed.get('error'),
                timestamp=datetime.now(timezone.utc),
                raw_data=raw_data
            )
        except json.JSONDecodeError as e:
            raise MCPTransportError(f"Invalid JSON message: {e}")

    def to_json(self) -> str:
        """Convert message to JSON string."""
        data = {"jsonrpc": "2.0"}
        if self.id is not None:
            data['id'] = self.id
        if self.method is not None:
            data['method'] = self.method
        if self.params is not None:
            data['params'] = self.params
        if self.result is not None:
            data['result'] = self.result
        if self.error is not None:
            data['error'] = self.error
        return json.dumps(data)


class MCPTransport(ABC):
    """Abstract base class for MCP transports."""
    
    def __init__(self, config: MCPTransportConfig):
        self.config = config
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        self._connected = False
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        """Check if transport is connected."""
        return self._connected

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the MCP server."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the MCP server."""
        pass

    @abstractmethod
    async def send_message(self, message: MCPMessage) -> None:
        """Send a message to the MCP server."""
        pass

    @abstractmethod
    async def receive_message(self) -> MCPMessage:
        """Receive a message from the MCP server."""
        pass

    @abstractmethod
    async def call(
        self, 
        method: str, 
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None
    ) -> Any:
        """Make a synchronous call to the MCP server."""
        pass

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()