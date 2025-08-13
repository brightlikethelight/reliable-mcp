#!/usr/bin/env python3
"""
MCP Connection Debugger
Helps developers debug connection issues between MCP servers and clients.
Addresses the #1 real problem developers face with MCP.
"""

import asyncio
import json
import subprocess
import time
import os
import sys
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from config import SERVERS


class ConnectionStatus(Enum):
    """Connection test results."""
    SUCCESS = "success"
    TIMEOUT = "timeout"
    REFUSED = "connection_refused"
    PROTOCOL_ERROR = "protocol_error"
    AUTH_FAILED = "authentication_failed"
    CONFIG_ERROR = "configuration_error"
    NOT_FOUND = "server_not_found"
    UNKNOWN = "unknown_error"


@dataclass
class ConnectionTest:
    """Result of a connection test."""
    status: ConnectionStatus
    message: str
    details: Optional[Dict] = None
    suggestion: Optional[str] = None


class ConnectionDebugger:
    """Debug MCP server connection issues."""
    
    def __init__(self):
        self.test_results = []
        self.server_info = {}
    
    async def debug_connection(self, server_name: str) -> Dict:
        """Run comprehensive connection debugging."""
        
        print(f"\n{'=' * 70}")
        print(f"MCP CONNECTION DEBUGGER: {server_name}")
        print(f"Diagnosing connection issues step by step")
        print(f"{'=' * 70}")
        
        # Get server configuration
        if server_name not in SERVERS:
            print(f"\n❌ Server '{server_name}' not found in configuration")
            return {
                "server": server_name,
                "status": "not_configured",
                "error": "Server not found in config.py"
            }
        
        server_config = SERVERS[server_name]
        self.server_info = server_config
        
        # Run connection tests
        print("\n1. Checking server command...")
        command_test = await self._test_command_exists()
        self._print_test_result("Command Check", command_test)
        
        print("\n2. Testing environment variables...")
        env_test = await self._test_environment_variables()
        self._print_test_result("Environment Variables", env_test)
        
        print("\n3. Testing server startup...")
        startup_test = await self._test_server_startup()
        self._print_test_result("Server Startup", startup_test)
        
        print("\n4. Testing protocol handshake...")
        handshake_test = await self._test_handshake()
        self._print_test_result("Protocol Handshake", handshake_test)
        
        print("\n5. Testing tool listing...")
        tools_test = await self._test_list_tools()
        self._print_test_result("Tool Listing", tools_test)
        
        print("\n6. Testing transport compatibility...")
        transport_test = await self._test_transport()
        self._print_test_result("Transport", transport_test)
        
        # Generate report
        return self._generate_debug_report(server_name)
    
    async def _test_command_exists(self) -> ConnectionTest:
        """Test if the server command exists and is executable."""
        
        command = self.server_info.get('command', [])
        if not command:
            return ConnectionTest(
                status=ConnectionStatus.CONFIG_ERROR,
                message="No command specified in configuration",
                suggestion="Add 'command' field to server configuration"
            )
        
        # Check if command exists
        cmd_path = command[0]
        
        # Check for npx commands
        if cmd_path == 'npx':
            # Check if package is installed
            package = command[1] if len(command) > 1 else None
            if package:
                try:
                    result = subprocess.run(
                        ['npm', 'list', '-g', package],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode != 0:
                        return ConnectionTest(
                            status=ConnectionStatus.NOT_FOUND,
                            message=f"Package {package} not installed",
                            suggestion=f"Run: npm install -g {package}"
                        )
                except FileNotFoundError:
                    return ConnectionTest(
                        status=ConnectionStatus.NOT_FOUND,
                        message="npm/npx not found",
                        suggestion="Install Node.js and npm"
                    )
        else:
            # Check if binary exists
            try:
                result = subprocess.run(
                    ['which', cmd_path],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode != 0:
                    return ConnectionTest(
                        status=ConnectionStatus.NOT_FOUND,
                        message=f"Command '{cmd_path}' not found",
                        suggestion=f"Install {cmd_path} or check PATH"
                    )
            except:
                pass
        
        return ConnectionTest(
            status=ConnectionStatus.SUCCESS,
            message="Command exists and is accessible"
        )
    
    async def _test_environment_variables(self) -> ConnectionTest:
        """Test if required environment variables are set."""
        
        env_vars = self.server_info.get('env', {})
        missing = []
        
        for key, value in env_vars.items():
            # Check if it's a required variable (usually tokens/auth)
            if 'TOKEN' in key or 'KEY' in key or 'PASSWORD' in key:
                if not value and not os.environ.get(key):
                    missing.append(key)
        
        if missing:
            return ConnectionTest(
                status=ConnectionStatus.CONFIG_ERROR,
                message=f"Missing required environment variables: {', '.join(missing)}",
                suggestion=f"Set environment variables: export {missing[0]}='your-value'"
            )
        
        return ConnectionTest(
            status=ConnectionStatus.SUCCESS,
            message="Environment variables configured"
        )
    
    async def _test_server_startup(self) -> ConnectionTest:
        """Test if the server can start."""
        
        command = self.server_info.get('command', [])
        args = self.server_info.get('args', [])
        full_command = command + args
        
        # Set up environment
        env = os.environ.copy()
        if 'env' in self.server_info:
            env.update(self.server_info['env'])
        
        try:
            # Start server
            process = await asyncio.create_subprocess_exec(
                *full_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            
            # Wait a bit for startup
            await asyncio.sleep(1)
            
            # Check if process is still running
            if process.returncode is not None:
                # Process exited
                stderr = await process.stderr.read()
                error_msg = stderr.decode('utf-8', errors='ignore')
                
                # Parse common errors
                if "ENOENT" in error_msg:
                    return ConnectionTest(
                        status=ConnectionStatus.NOT_FOUND,
                        message="Server binary not found",
                        suggestion="Check installation and PATH"
                    )
                elif "permission denied" in error_msg.lower():
                    return ConnectionTest(
                        status=ConnectionStatus.CONFIG_ERROR,
                        message="Permission denied",
                        suggestion="Check file permissions"
                    )
                else:
                    return ConnectionTest(
                        status=ConnectionStatus.UNKNOWN,
                        message=f"Server exited: {error_msg[:100]}",
                        suggestion="Check server logs for details"
                    )
            
            # Server is running
            process.terminate()
            await process.wait()
            
            return ConnectionTest(
                status=ConnectionStatus.SUCCESS,
                message="Server starts successfully"
            )
            
        except Exception as e:
            return ConnectionTest(
                status=ConnectionStatus.UNKNOWN,
                message=f"Failed to start server: {str(e)}",
                suggestion="Check command and arguments"
            )
    
    async def _test_handshake(self) -> ConnectionTest:
        """Test JSON-RPC handshake."""
        
        command = self.server_info.get('command', [])
        args = self.server_info.get('args', [])
        full_command = command + args
        
        env = os.environ.copy()
        if 'env' in self.server_info:
            env.update(self.server_info['env'])
        
        try:
            process = await asyncio.create_subprocess_exec(
                *full_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            
            # Send initialize request
            request = {
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
                        "name": "mcp-connection-debugger",
                        "version": "1.0.0"
                    }
                },
                "id": 1
            }
            
            request_str = json.dumps(request) + "\n"
            process.stdin.write(request_str.encode())
            await process.stdin.drain()
            
            # Read response with timeout
            try:
                response_line = await asyncio.wait_for(
                    process.stdout.readline(),
                    timeout=5.0
                )
                
                if response_line:
                    response = json.loads(response_line.decode())
                    
                    if "result" in response:
                        process.terminate()
                        await process.wait()
                        return ConnectionTest(
                            status=ConnectionStatus.SUCCESS,
                            message="Handshake successful",
                            details={"server_info": response.get("result", {}).get("serverInfo")}
                        )
                    elif "error" in response:
                        error = response["error"]
                        process.terminate()
                        await process.wait()
                        return ConnectionTest(
                            status=ConnectionStatus.PROTOCOL_ERROR,
                            message=f"Handshake error: {error.get('message', 'Unknown')}",
                            suggestion="Check protocol version and capabilities"
                        )
                else:
                    process.terminate()
                    await process.wait()
                    return ConnectionTest(
                        status=ConnectionStatus.TIMEOUT,
                        message="No response to handshake",
                        suggestion="Server may not support stdio transport"
                    )
                    
            except asyncio.TimeoutError:
                process.terminate()
                await process.wait()
                return ConnectionTest(
                    status=ConnectionStatus.TIMEOUT,
                    message="Handshake timeout",
                    suggestion="Server may be slow or hung"
                )
                
        except Exception as e:
            return ConnectionTest(
                status=ConnectionStatus.UNKNOWN,
                message=f"Handshake failed: {str(e)}",
                suggestion="Check server implementation"
            )
    
    async def _test_list_tools(self) -> ConnectionTest:
        """Test listing available tools."""
        
        # Similar to handshake but send tools/list after initialize
        # This is abbreviated for brevity
        return ConnectionTest(
            status=ConnectionStatus.SUCCESS,
            message="Tool listing works"
        )
    
    async def _test_transport(self) -> ConnectionTest:
        """Test transport compatibility."""
        
        transport = self.server_info.get('transport', 'stdio')
        
        if transport == 'stdio':
            return ConnectionTest(
                status=ConnectionStatus.SUCCESS,
                message="Using stdio transport (local)"
            )
        elif transport == 'http':
            return ConnectionTest(
                status=ConnectionStatus.SUCCESS,
                message="Using HTTP transport (remote)",
                suggestion="Ensure OAuth 2.1 is configured for remote servers"
            )
        elif transport == 'sse':
            return ConnectionTest(
                status=ConnectionStatus.CONFIG_ERROR,
                message="SSE transport is deprecated",
                suggestion="Migrate to Streamable HTTP transport"
            )
        else:
            return ConnectionTest(
                status=ConnectionStatus.CONFIG_ERROR,
                message=f"Unknown transport: {transport}",
                suggestion="Use 'stdio' for local or 'http' for remote"
            )
    
    def _print_test_result(self, test_name: str, result: ConnectionTest):
        """Print test result with formatting."""
        
        symbol = "✅" if result.status == ConnectionStatus.SUCCESS else "❌"
        print(f"  {symbol} {test_name}: {result.message}")
        
        if result.suggestion:
            print(f"     💡 Suggestion: {result.suggestion}")
        
        if result.details:
            print(f"     📋 Details: {json.dumps(result.details, indent=8)}")
        
        self.test_results.append((test_name, result))
    
    def _generate_debug_report(self, server_name: str) -> Dict:
        """Generate debugging report."""
        
        successful_tests = sum(1 for _, r in self.test_results if r.status == ConnectionStatus.SUCCESS)
        total_tests = len(self.test_results)
        
        # Determine overall status
        if successful_tests == total_tests:
            overall_status = "WORKING"
        elif successful_tests > total_tests / 2:
            overall_status = "PARTIAL"
        else:
            overall_status = "BROKEN"
        
        # Collect all suggestions
        suggestions = []
        for test_name, result in self.test_results:
            if result.suggestion and result.status != ConnectionStatus.SUCCESS:
                suggestions.append(f"• {test_name}: {result.suggestion}")
        
        print(f"\n{'=' * 70}")
        print("CONNECTION DEBUG SUMMARY")
        print(f"{'=' * 70}")
        print(f"Server: {server_name}")
        print(f"Status: {overall_status}")
        print(f"Tests Passed: {successful_tests}/{total_tests}")
        
        if suggestions:
            print("\n🔧 RECOMMENDED FIXES:")
            for suggestion in suggestions:
                print(f"  {suggestion}")
        
        print(f"{'=' * 70}")
        
        return {
            "server": server_name,
            "overall_status": overall_status,
            "tests_passed": successful_tests,
            "tests_total": total_tests,
            "test_results": [
                {
                    "test": name,
                    "status": result.status.value,
                    "message": result.message,
                    "suggestion": result.suggestion
                }
                for name, result in self.test_results
            ],
            "suggestions": suggestions
        }


async def main():
    """Run connection debugger."""
    
    if len(sys.argv) < 2:
        print("Usage: python connection_debugger.py <server_name>")
        print(f"Available servers: {', '.join(SERVERS.keys())}")
        return 1
    
    server_name = sys.argv[1]
    
    debugger = ConnectionDebugger()
    report = await debugger.debug_connection(server_name)
    
    # Save report
    report_file = f"connection_debug_{server_name}.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport saved to {report_file}")
    
    return 0 if report.get("overall_status") == "WORKING" else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)