#!/usr/bin/env python3
"""
MCP Error Message Decoder
Helps developers understand cryptic MCP error messages and provides actionable solutions.
Addresses the real frustration of debugging "Cannot read properties of undefined" and similar errors.
"""

import re
import json
import sys
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ErrorCategory(Enum):
    """Categories of MCP errors."""
    CONNECTION = "connection"
    PROTOCOL = "protocol"
    SCHEMA = "schema"
    AUTHENTICATION = "authentication"
    TIMEOUT = "timeout"
    RESOURCE = "resource"
    CONFIGURATION = "configuration"
    UNKNOWN = "unknown"


@dataclass
class ErrorSolution:
    """Solution for an error."""
    description: str
    steps: List[str]
    example: Optional[str] = None
    documentation_link: Optional[str] = None


@dataclass
class DecodedError:
    """Decoded error with solutions."""
    original_error: str
    category: ErrorCategory
    simplified_message: str
    likely_cause: str
    solutions: List[ErrorSolution]
    related_errors: List[str]


class ErrorDecoder:
    """Decode and explain MCP error messages."""
    
    # Common error patterns and their explanations
    ERROR_PATTERNS = {
        # Schema/Type Errors
        r"Cannot read propert(?:y|ies) (?:of|from) (?:undefined|null)": {
            "category": ErrorCategory.SCHEMA,
            "message": "Missing required field in response",
            "cause": "Server returned incomplete data or client expected different schema",
            "solutions": [
                ErrorSolution(
                    "Check server response structure",
                    [
                        "Enable debug logging to see raw responses",
                        "Verify server implements all required fields",
                        "Check for version mismatch between client and server"
                    ],
                    example="Ensure 'tools' field exists in response and is an array"
                )
            ]
        },
        
        r"TypeError.*undefined is not.*": {
            "category": ErrorCategory.SCHEMA,
            "message": "Type error due to undefined value",
            "cause": "Trying to access property on undefined object",
            "solutions": [
                ErrorSolution(
                    "Add null checks",
                    [
                        "Check if object exists before accessing properties",
                        "Use optional chaining (?.) in JavaScript/TypeScript",
                        "Provide default values for optional fields"
                    ],
                    example="const value = response?.data?.field || defaultValue"
                )
            ]
        },
        
        # Connection Errors
        r"ECONNREFUSED.*127\.0\.0\.1:(\d+)": {
            "category": ErrorCategory.CONNECTION,
            "message": "Connection refused on local port",
            "cause": "Server is not running or listening on wrong port",
            "solutions": [
                ErrorSolution(
                    "Start the server",
                    [
                        "Check if server process is running",
                        "Verify server is listening on correct port",
                        "Check for port conflicts with other services"
                    ],
                    example="lsof -i :PORT_NUMBER to check if port is in use"
                )
            ]
        },
        
        r"ENOENT.*spawn.*ENOENT": {
            "category": ErrorCategory.CONFIGURATION,
            "message": "Command not found",
            "cause": "Executable or script specified in configuration doesn't exist",
            "solutions": [
                ErrorSolution(
                    "Fix command path",
                    [
                        "Check if command is installed (npm install -g ...)",
                        "Verify PATH environment variable includes command location",
                        "Use absolute path to executable"
                    ],
                    example="which npx  # Check if npx is in PATH"
                )
            ]
        },
        
        # Protocol Errors
        r"Invalid JSON-RPC.*version": {
            "category": ErrorCategory.PROTOCOL,
            "message": "JSON-RPC version mismatch",
            "cause": "Client and server using different protocol versions",
            "solutions": [
                ErrorSolution(
                    "Update protocol version",
                    [
                        "Ensure both use JSON-RPC 2.0",
                        "Update server/client to latest version",
                        "Check 'jsonrpc' field is '2.0' in all messages"
                    ]
                )
            ]
        },
        
        r"Method.*not found": {
            "category": ErrorCategory.PROTOCOL,
            "message": "RPC method not implemented",
            "cause": "Server doesn't implement requested method",
            "solutions": [
                ErrorSolution(
                    "Check server capabilities",
                    [
                        "List available methods with 'tools/list'",
                        "Verify server version supports this method",
                        "Check method name spelling and case"
                    ]
                )
            ]
        },
        
        # Authentication Errors
        r"(?:401|Unauthorized|Authentication failed)": {
            "category": ErrorCategory.AUTHENTICATION,
            "message": "Authentication failed",
            "cause": "Missing or invalid credentials",
            "solutions": [
                ErrorSolution(
                    "Fix authentication",
                    [
                        "Set API_KEY or TOKEN environment variable",
                        "Check credential format and encoding",
                        "Verify credentials haven't expired"
                    ],
                    example="export MCP_API_KEY='your-api-key'"
                )
            ]
        },
        
        # Timeout Errors
        r"(?:Timeout|Timed out|ETIMEDOUT)": {
            "category": ErrorCategory.TIMEOUT,
            "message": "Operation timed out",
            "cause": "Server took too long to respond",
            "solutions": [
                ErrorSolution(
                    "Increase timeout",
                    [
                        "Increase client timeout setting",
                        "Check server performance and load",
                        "Verify network connectivity"
                    ],
                    example="client.timeout = 30000  # 30 seconds"
                )
            ]
        },
        
        # Resource Errors
        r"(?:EMFILE|Too many open files)": {
            "category": ErrorCategory.RESOURCE,
            "message": "Too many open files",
            "cause": "File descriptor limit reached",
            "solutions": [
                ErrorSolution(
                    "Increase file limits",
                    [
                        "Increase ulimit: ulimit -n 4096",
                        "Close unused file handles",
                        "Check for file descriptor leaks"
                    ]
                )
            ]
        },
        
        r"(?:ENOMEM|Out of memory)": {
            "category": ErrorCategory.RESOURCE,
            "message": "Out of memory",
            "cause": "Process ran out of available memory",
            "solutions": [
                ErrorSolution(
                    "Reduce memory usage",
                    [
                        "Increase Node.js heap size: --max-old-space-size=4096",
                        "Process data in smaller batches",
                        "Check for memory leaks"
                    ]
                )
            ]
        }
    }
    
    # Common error messages and their plain English explanations
    COMMON_ERRORS = {
        "Cannot read properties of undefined (reading 'tools')": {
            "plain": "The server didn't return a 'tools' field in its response",
            "fix": "Check server implementation returns {tools: [...]} in response"
        },
        "spawn npx ENOENT": {
            "plain": "Can't find 'npx' command",
            "fix": "Install Node.js/npm or add to PATH"
        },
        "EADDRINUSE: address already in use": {
            "plain": "Another process is using this port",
            "fix": "Kill the other process or use a different port"
        },
        "Invalid client configuration": {
            "plain": "Configuration file has wrong format",
            "fix": "Check if using correct format for your client (Claude Desktop, Cursor, etc)"
        },
        "Handshake timeout": {
            "plain": "Server didn't respond to initial connection",
            "fix": "Check if server supports stdio transport and is starting correctly"
        }
    }
    
    def decode_error(self, error_message: str) -> DecodedError:
        """Decode an error message into actionable information."""
        
        # Check for exact match in common errors
        for common_error, info in self.COMMON_ERRORS.items():
            if common_error.lower() in error_message.lower():
                return DecodedError(
                    original_error=error_message,
                    category=ErrorCategory.UNKNOWN,
                    simplified_message=info["plain"],
                    likely_cause=info["plain"],
                    solutions=[
                        ErrorSolution(
                            description=info["fix"],
                            steps=[info["fix"]]
                        )
                    ],
                    related_errors=[]
                )
        
        # Check patterns
        for pattern, info in self.ERROR_PATTERNS.items():
            if re.search(pattern, error_message, re.IGNORECASE):
                return DecodedError(
                    original_error=error_message,
                    category=info["category"],
                    simplified_message=info["message"],
                    likely_cause=info["cause"],
                    solutions=info["solutions"],
                    related_errors=self._find_related_errors(info["category"])
                )
        
        # Unknown error - provide generic help
        return self._decode_unknown_error(error_message)
    
    def _decode_unknown_error(self, error_message: str) -> DecodedError:
        """Provide generic help for unknown errors."""
        
        # Try to categorize based on keywords
        category = ErrorCategory.UNKNOWN
        
        if any(word in error_message.lower() for word in ["connect", "refused", "enoent"]):
            category = ErrorCategory.CONNECTION
        elif any(word in error_message.lower() for word in ["undefined", "null", "type"]):
            category = ErrorCategory.SCHEMA
        elif any(word in error_message.lower() for word in ["auth", "401", "forbidden"]):
            category = ErrorCategory.AUTHENTICATION
        elif any(word in error_message.lower() for word in ["timeout", "timed"]):
            category = ErrorCategory.TIMEOUT
        
        return DecodedError(
            original_error=error_message,
            category=category,
            simplified_message="Unknown error type",
            likely_cause="Error pattern not recognized",
            solutions=[
                ErrorSolution(
                    description="General debugging steps",
                    steps=[
                        "Enable debug logging to see full error context",
                        "Check server logs for more details",
                        "Try with a simpler configuration first",
                        "Verify all dependencies are installed",
                        "Check GitHub issues for similar problems"
                    ]
                )
            ],
            related_errors=self._find_related_errors(category)
        )
    
    def _find_related_errors(self, category: ErrorCategory) -> List[str]:
        """Find related errors in the same category."""
        
        related = []
        for pattern, info in self.ERROR_PATTERNS.items():
            if info["category"] == category:
                related.append(info["message"])
        
        return related[:3]  # Return top 3 related errors
    
    def suggest_debug_commands(self, error: DecodedError) -> List[str]:
        """Suggest debug commands based on error type."""
        
        commands = []
        
        if error.category == ErrorCategory.CONNECTION:
            commands.extend([
                "# Check if server is running",
                "ps aux | grep [server_name]",
                "",
                "# Check port availability",
                "lsof -i :PORT",
                "",
                "# Test connection",
                "nc -zv localhost PORT"
            ])
        
        elif error.category == ErrorCategory.CONFIGURATION:
            commands.extend([
                "# Validate configuration",
                "python config_validator.py [config_file]",
                "",
                "# Check command exists",
                "which [command]",
                "",
                "# Check environment variables",
                "env | grep MCP"
            ])
        
        elif error.category == ErrorCategory.SCHEMA:
            commands.extend([
                "# Test with debug logging",
                "DEBUG=* [command]",
                "",
                "# Validate schema",
                "python schema_chaos_validator.py [server]",
                "",
                "# Check protocol compliance",
                "python mcp_protocol_validator.py [server]"
            ])
        
        elif error.category == ErrorCategory.AUTHENTICATION:
            commands.extend([
                "# Check authentication",
                "python auth_tester.py [server]",
                "",
                "# Test with credentials",
                "export MCP_API_KEY='test-key'",
                "[command]"
            ])
        
        elif error.category == ErrorCategory.TIMEOUT:
            commands.extend([
                "# Test with increased timeout",
                "TIMEOUT=60000 [command]",
                "",
                "# Check server performance",
                "python benchmarking/benchmark_runner.py --quick"
            ])
        
        return commands


def print_decoded_error(decoded: DecodedError):
    """Print decoded error in a friendly format."""
    
    print(f"\n{'=' * 70}")
    print("ERROR DECODED")
    print(f"{'=' * 70}")
    
    print(f"\n📝 Original Error:")
    # Truncate if too long
    if len(decoded.original_error) > 200:
        print(f"  {decoded.original_error[:200]}...")
    else:
        print(f"  {decoded.original_error}")
    
    print(f"\n🏷️ Category: {decoded.category.value.upper()}")
    
    print(f"\n💬 Plain English:")
    print(f"  {decoded.simplified_message}")
    
    print(f"\n🔍 Likely Cause:")
    print(f"  {decoded.likely_cause}")
    
    print(f"\n💡 Solutions:")
    for i, solution in enumerate(decoded.solutions, 1):
        print(f"\n  Solution {i}: {solution.description}")
        for step in solution.steps:
            print(f"    • {step}")
        if solution.example:
            print(f"    Example: {solution.example}")
    
    if decoded.related_errors:
        print(f"\n🔗 Related Errors:")
        for error in decoded.related_errors:
            print(f"  • {error}")
    
    print(f"\n{'=' * 70}")


def interactive_mode():
    """Interactive error decoder mode."""
    
    decoder = ErrorDecoder()
    
    print("\n" + "=" * 70)
    print("MCP ERROR DECODER - Interactive Mode")
    print("=" * 70)
    print("\nPaste your error message (press Enter twice to decode):")
    
    while True:
        print("\n> ", end="")
        lines = []
        
        # Read multi-line input
        while True:
            line = input()
            if not line and lines:  # Empty line after content
                break
            if line:
                lines.append(line)
        
        if not lines:
            print("Type 'exit' to quit or paste an error message")
            continue
        
        error_text = "\n".join(lines)
        
        if error_text.lower() == 'exit':
            break
        
        # Decode the error
        decoded = decoder.decode_error(error_text)
        print_decoded_error(decoded)
        
        # Suggest debug commands
        commands = decoder.suggest_debug_commands(decoded)
        if commands:
            print("\n🛠️ Debug Commands to Try:")
            for cmd in commands:
                print(f"  {cmd}")
        
        print("\n" + "=" * 70)
        print("Paste another error or type 'exit' to quit")


def main():
    """Run error decoder."""
    
    if len(sys.argv) > 1:
        # Decode error from command line
        error_message = " ".join(sys.argv[1:])
        
        decoder = ErrorDecoder()
        decoded = decoder.decode_error(error_message)
        print_decoded_error(decoded)
        
        # Suggest debug commands
        commands = decoder.suggest_debug_commands(decoded)
        if commands:
            print("\n🛠️ Debug Commands to Try:")
            for cmd in commands:
                print(f"  {cmd}")
    else:
        # Interactive mode
        interactive_mode()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())