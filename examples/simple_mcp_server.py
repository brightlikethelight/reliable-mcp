#!/usr/bin/env python3
"""
Simple MCP Server for testing the reliability lab.

This server implements basic MCP protocol over STDIO with several tools
for demonstrating different testing scenarios.
"""

import asyncio
import json
import sys
import logging
import tempfile
import random
from typing import Dict, Any, Optional
from pathlib import Path
import traceback


# Configure logging to stderr to avoid interfering with STDIO protocol
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimpleMCPServer:
    """Simple MCP server with basic tool implementations."""
    
    def __init__(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="mcp_test_"))
        logger.info(f"Created temp directory: {self.temp_dir}")
        
        # Tool implementations
        self.tools = {
            "calculator": self._calculator_tool,
            "weather": self._weather_tool,
            "file_ops": self._file_ops_tool,
            "error_simulator": self._error_simulator_tool
        }
        
        # Tool definitions for tools/list
        self.tool_definitions = {
            "calculator": {
                "name": "calculator",
                "description": "Perform basic arithmetic operations",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["add", "subtract", "multiply", "divide"],
                            "description": "The arithmetic operation to perform"
                        },
                        "a": {
                            "type": "number",
                            "description": "First operand"
                        },
                        "b": {
                            "type": "number", 
                            "description": "Second operand"
                        }
                    },
                    "required": ["operation", "a", "b"]
                }
            },
            "weather": {
                "name": "weather",
                "description": "Get weather information for a location",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The location to get weather for"
                        },
                        "days": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 7,
                            "default": 1,
                            "description": "Number of days to forecast"
                        }
                    },
                    "required": ["location"]
                }
            },
            "file_ops": {
                "name": "file_ops",
                "description": "Perform file operations in a safe temporary directory",
                "inputSchema": {
                    "type": "object", 
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["create", "read", "delete", "list"],
                            "description": "The file operation to perform"
                        },
                        "filename": {
                            "type": "string",
                            "description": "The filename (required for create, read, delete)"
                        },
                        "content": {
                            "type": "string",
                            "description": "File content (required for create)"
                        }
                    },
                    "required": ["operation"]
                }
            },
            "error_simulator": {
                "name": "error_simulator",
                "description": "Simulate various error conditions for testing",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "error_type": {
                            "type": "string",
                            "enum": ["timeout", "invalid_params", "internal_error", "random"],
                            "description": "Type of error to simulate"
                        },
                        "delay": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 30,
                            "default": 1,
                            "description": "Delay in seconds before responding"
                        }
                    },
                    "required": ["error_type"]
                }
            }
        }

    async def _calculator_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Calculator tool implementation."""
        operation = arguments.get("operation")
        a = arguments.get("a")
        b = arguments.get("b")
        
        logger.info(f"Calculator: {operation}({a}, {b})")
        
        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        elif operation == "multiply":
            result = a * b
        elif operation == "divide":
            if b == 0:
                raise ValueError("Division by zero")
            result = a / b
        else:
            raise ValueError(f"Unknown operation: {operation}")
        
        return {
            "content": [{
                "type": "text",
                "text": f"Result: {a} {operation} {b} = {result}"
            }],
            "isError": False
        }

    async def _weather_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Weather tool implementation with simulated data."""
        location = arguments.get("location", "Unknown")
        days = arguments.get("days", 1)
        
        logger.info(f"Weather: {location} for {days} days")
        
        # Simulate weather data
        conditions = ["sunny", "cloudy", "rainy", "snowy", "foggy"]
        forecast = []
        
        for day in range(days):
            temp = random.randint(-10, 35)  # Celsius
            condition = random.choice(conditions)
            humidity = random.randint(30, 90)
            
            forecast.append({
                "day": day + 1,
                "temperature": temp,
                "condition": condition,
                "humidity": humidity
            })
        
        return {
            "content": [{
                "type": "text",
                "text": f"Weather forecast for {location}:\n" + 
                       "\n".join([
                           f"Day {f['day']}: {f['temperature']}°C, {f['condition']}, {f['humidity']}% humidity"
                           for f in forecast
                       ])
            }],
            "isError": False
        }

    async def _file_ops_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """File operations tool implementation."""
        operation = arguments.get("operation")
        filename = arguments.get("filename")
        content = arguments.get("content")
        
        logger.info(f"File ops: {operation} on {filename}")
        
        if operation == "list":
            files = list(self.temp_dir.glob("*"))
            return {
                "content": [{
                    "type": "text", 
                    "text": f"Files in temp directory:\n" + 
                           "\n".join([f.name for f in files if f.is_file()])
                }],
                "isError": False
            }
        
        if not filename:
            raise ValueError("filename required for this operation")
            
        file_path = self.temp_dir / filename
        
        if operation == "create":
            if not content:
                raise ValueError("content required for create operation")
            file_path.write_text(content)
            return {
                "content": [{
                    "type": "text",
                    "text": f"Created file '{filename}' with {len(content)} characters"
                }],
                "isError": False
            }
            
        elif operation == "read":
            if not file_path.exists():
                raise FileNotFoundError(f"File '{filename}' not found")
            content = file_path.read_text()
            return {
                "content": [{
                    "type": "text",
                    "text": f"Content of '{filename}':\n{content}"
                }],
                "isError": False
            }
            
        elif operation == "delete":
            if not file_path.exists():
                raise FileNotFoundError(f"File '{filename}' not found")
            file_path.unlink()
            return {
                "content": [{
                    "type": "text",
                    "text": f"Deleted file '{filename}'"
                }],
                "isError": False
            }
        
        else:
            raise ValueError(f"Unknown operation: {operation}")

    async def _error_simulator_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Error simulator tool for testing error handling."""
        error_type = arguments.get("error_type")
        delay = arguments.get("delay", 1)
        
        logger.info(f"Error simulator: {error_type} with {delay}s delay")
        
        # Apply delay
        if delay > 0:
            await asyncio.sleep(delay)
        
        if error_type == "timeout":
            # Simulate a timeout by sleeping longer than expected
            await asyncio.sleep(10)
            return {"content": [{"type": "text", "text": "This shouldn't be reached"}], "isError": False}
            
        elif error_type == "invalid_params":
            raise ValueError("Simulated invalid parameters error")
            
        elif error_type == "internal_error":
            raise RuntimeError("Simulated internal server error")
            
        elif error_type == "random":
            if random.random() < 0.5:
                raise Exception(f"Random error {random.randint(1, 100)}")
            return {
                "content": [{
                    "type": "text",
                    "text": "Random error simulation passed!"
                }],
                "isError": False
            }
        
        else:
            raise ValueError(f"Unknown error type: {error_type}")

    async def handle_message(self, message: str) -> Optional[str]:
        """Handle incoming JSON-RPC message."""
        try:
            data = json.loads(message.strip())
            logger.debug(f"Received message: {data}")
            
            # Handle initialize request
            if data.get("method") == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "simple-mcp-server",
                            "version": "1.0.0"
                        }
                    }
                }
                return json.dumps(response)
            
            # Handle initialized notification
            elif data.get("method") == "initialized":
                logger.info("Server initialized")
                return None
            
            # Handle tools/list request
            elif data.get("method") == "tools/list":
                response = {
                    "jsonrpc": "2.0", 
                    "id": data.get("id"),
                    "result": {
                        "tools": list(self.tool_definitions.values())
                    }
                }
                return json.dumps(response)
            
            # Handle tools/call request
            elif data.get("method") == "tools/call":
                params = data.get("params", {})
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                if tool_name not in self.tools:
                    response = {
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "error": {
                            "code": -32601,
                            "message": f"Unknown tool: {tool_name}"
                        }
                    }
                    return json.dumps(response)
                
                try:
                    result = await self.tools[tool_name](arguments)
                    response = {
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "result": result
                    }
                    return json.dumps(response)
                    
                except Exception as e:
                    logger.error(f"Tool error: {e}", exc_info=True)
                    response = {
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "error": {
                            "code": -32603,
                            "message": str(e),
                            "data": {
                                "traceback": traceback.format_exc()
                            }
                        }
                    }
                    return json.dumps(response)
            
            # Unknown method
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {data.get('method')}"
                    }
                }
                return json.dumps(response)
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {e}"
                }
            }
            return json.dumps(response)
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            response = {
                "jsonrpc": "2.0",
                "id": data.get("id") if "data" in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {e}"
                }
            }
            return json.dumps(response)

    async def run(self):
        """Main server loop."""
        logger.info("Starting Simple MCP Server")
        
        try:
            while True:
                line = await asyncio.to_thread(sys.stdin.readline)
                if not line:
                    logger.info("EOF received, shutting down")
                    break
                    
                response = await self.handle_message(line)
                if response:
                    print(response, flush=True)
                    
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Server error: {e}", exc_info=True)
        finally:
            # Clean up temp directory
            import shutil
            try:
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temp directory: {self.temp_dir}")
            except Exception as e:
                logger.error(f"Error cleaning up temp directory: {e}")


async def main():
    """Main entry point."""
    server = SimpleMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())