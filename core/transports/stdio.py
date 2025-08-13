"""STDIO transport implementation for MCP communication."""

import asyncio
import subprocess
import json
from typing import Dict, Any, Optional
import uuid
from datetime import datetime, timezone

from ..transport import MCPTransport, MCPMessage
from ..config import StdioTransportConfig
from ..errors import MCPConnectionError, MCPTimeoutError, MCPTransportError


class StdioTransport(MCPTransport):
    """STDIO-based transport for MCP communication."""
    
    def __init__(self, config: StdioTransportConfig):
        super().__init__(config)
        self.config: StdioTransportConfig = config
        self.process: Optional[asyncio.subprocess.Process] = None
        self._pending_calls: Dict[str, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        """Start the MCP server process."""
        async with self._lock:
            if self._connected:
                return

            try:
                self.process = await asyncio.create_subprocess_exec(
                    *self.config.command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.config.working_directory,
                    env=self.config.environment_variables or None,
                    limit=self.config.buffer_size
                )
                
                self._connected = True
                self._reader_task = asyncio.create_task(self._read_loop())
                self.logger.info("STDIO transport connected")
                
            except Exception as e:
                raise MCPConnectionError(f"Failed to start MCP server: {e}")

    async def disconnect(self) -> None:
        """Stop the MCP server process."""
        async with self._lock:
            if not self._connected:
                return

            if self._reader_task:
                self._reader_task.cancel()
                try:
                    await self._reader_task
                except asyncio.CancelledError:
                    pass

            if self.process:
                self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    self.process.kill()
                    await self.process.wait()

            # Cancel all pending calls
            for future in self._pending_calls.values():
                if not future.done():
                    future.set_exception(MCPConnectionError("Transport disconnected"))
            self._pending_calls.clear()

            self._connected = False
            self.process = None
            self.logger.info("STDIO transport disconnected")

    async def send_message(self, message: MCPMessage) -> None:
        """Send a message via STDIO."""
        if not self._connected or not self.process:
            raise MCPConnectionError("Transport not connected")

        try:
            data = message.to_json() + '\n'
            self.process.stdin.write(data.encode())
            await self.process.stdin.drain()
        except Exception as e:
            raise MCPTransportError(f"Failed to send message: {e}")

    async def receive_message(self) -> MCPMessage:
        """Receive a message via STDIO."""
        if not self._connected or not self.process:
            raise MCPConnectionError("Transport not connected")

        try:
            line = await asyncio.wait_for(
                self.process.stdout.readline(),
                timeout=self.config.timeout_config.read_timeout
            )
            
            if not line:
                raise MCPConnectionError("Server process terminated")
                
            return MCPMessage.from_json(line)
        except asyncio.TimeoutError:
            raise MCPTimeoutError("Timeout waiting for message")
        except Exception as e:
            raise MCPTransportError(f"Failed to receive message: {e}")

    async def call(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None
    ) -> Any:
        """Make a synchronous call via STDIO."""
        call_id = str(uuid.uuid4())
        timeout = timeout or self.config.timeout_config.call_timeout

        message = MCPMessage(
            id=call_id,
            method=method,
            params=params,
            result=None,
            error=None,
            timestamp=datetime.now(timezone.utc),
            raw_data=b''
        )

        # Set up future for response
        future = asyncio.Future()
        self._pending_calls[call_id] = future

        try:
            await self.send_message(message)
            response = await asyncio.wait_for(future, timeout=timeout)
            
            if 'error' in response and response['error'] is not None:
                raise MCPTransportError(f"Server error: {response['error']}")
                
            return response.get('result')
            
        except asyncio.TimeoutError:
            raise MCPTimeoutError(f"Call to {method} timed out after {timeout}s")
        finally:
            self._pending_calls.pop(call_id, None)

    async def _read_loop(self) -> None:
        """Background task to read messages and handle responses."""
        while self._connected:
            try:
                message = await self.receive_message()
                
                # Handle response messages
                if message.id and message.id in self._pending_calls:
                    future = self._pending_calls[message.id]
                    if not future.done():
                        future.set_result({
                            'result': message.result,
                            'error': message.error
                        })
                        
            except Exception as e:
                self.logger.error(f"Error in read loop: {e}")
                if self._connected:
                    # Attempt to reconnect or handle error
                    await asyncio.sleep(1.0)