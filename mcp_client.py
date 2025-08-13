#!/usr/bin/env python3
"""
Unified MCP Client for MCP Reliability Lab.
This is the single, clean implementation that consolidates all the duplicate versions.
"""

import asyncio
import json
import subprocess
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from config import TEST_DIR, SERVERS

logger = logging.getLogger(__name__)


class MCPClient:
    """Unified MCP client with all necessary functionality."""
    
    def __init__(self, server_type: str = "filesystem", server_params: Optional[Dict] = None):
        """Initialize MCP client.
        
        Args:
            server_type: Type of MCP server (filesystem, github, etc.)
            server_params: Optional parameters for the server
        """
        self.server_type = server_type
        self.server_params = server_params or {}
        self.process = None
        self.request_id = 1
        
        # Get server configuration
        if server_type in SERVERS:
            self.server_config = SERVERS[server_type].copy()
        else:
            # Default filesystem configuration
            self.server_config = {
                'command': ['npx', '@modelcontextprotocol/server-filesystem'],
                'args': [TEST_DIR],
                'path': TEST_DIR
            }
        
        # Override with provided params
        if 'working_dir' in self.server_params:
            self.server_config['path'] = self.server_params['working_dir']
            self.server_config['args'] = [self.server_params['working_dir']]
    
    async def start(self):
        """Start the MCP server process."""
        if self.process:
            logger.warning("Server already running")
            return
        
        cmd = self.server_config['command'] + self.server_config['args']
        logger.info(f"Starting MCP server: {' '.join(cmd)}")
        
        # Set up environment variables if specified
        env = None
        if 'env' in self.server_config:
            import os
            env = os.environ.copy()
            env.update(self.server_config['env'])
        
        try:
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            
            # Initialize connection with required protocol fields
            await self._send_request({
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "1.0.0",
                    "capabilities": {
                        "tools": True,
                        "resources": True,
                        "prompts": True
                    },
                    "clientInfo": {
                        "name": "mcp-reliability-lab",
                        "version": "1.0.0"
                    }
                },
                "id": self.request_id
            })
            self.request_id += 1
            
            logger.info(f"MCP server {self.server_type} started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            raise
    
    async def stop(self):
        """Stop the MCP server process."""
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
            self.process = None
            logger.info(f"MCP server {self.server_type} stopped")
    
    async def _send_request(self, request: Dict) -> Dict:
        """Send a JSON-RPC request to the server."""
        if not self.process:
            raise RuntimeError("Server not started")
        
        request_str = json.dumps(request) + "\n"
        self.process.stdin.write(request_str.encode())
        await self.process.stdin.drain()
        
        # Read response
        response_line = await self.process.stdout.readline()
        if not response_line:
            raise RuntimeError("No response from server")
        
        response = json.loads(response_line.decode())
        
        if "error" in response:
            raise RuntimeError(f"Server error: {response['error']}")
        
        return response.get("result", {})
    
    async def list_tools(self) -> List[Dict]:
        """List available tools from the MCP server."""
        result = await self._send_request({
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": self.request_id
        })
        self.request_id += 1
        return result.get("tools", [])
    
    async def call_tool(self, name: str, arguments: Dict) -> Dict:
        """Call an MCP tool.
        
        Args:
            name: Tool name
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        result = await self._send_request({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments
            },
            "id": self.request_id
        })
        self.request_id += 1
        return result
    
    async def call_tool_with_retry(self, name: str, arguments: Dict, retries: int = 3) -> Dict:
        """Call tool with retry logic.
        
        Args:
            name: Tool name
            arguments: Tool arguments
            retries: Number of retry attempts
            
        Returns:
            Tool execution result
        """
        last_error = None
        
        for attempt in range(retries):
            try:
                result = await self.call_tool(name, arguments)
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1}/{retries} failed: {e}")
                
                if attempt < retries - 1:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
        
        raise last_error
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()


# Backward compatibility
MinimalMCPClient = MCPClient  # Alias for compatibility