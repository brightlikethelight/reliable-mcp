#!/usr/bin/env python3
"""
MCP Protocol Validator
Validates Model Context Protocol server compliance with JSON-RPC 2.0 spec.
First tool to actually validate MCP protocol implementation.
"""

import asyncio
import json
import subprocess
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from asyncio.subprocess import Process


class ValidationLevel(Enum):
    """Validation severity levels."""
    ERROR = "error"      # Protocol violation
    WARNING = "warning"  # Best practice violation
    INFO = "info"       # Recommendation


@dataclass
class ValidationResult:
    """Result of a validation check."""
    level: ValidationLevel
    check: str
    message: str
    details: Optional[Dict] = None


@dataclass
class ProtocolReport:
    """Complete protocol validation report."""
    server_name: str
    timestamp: str
    passed: bool
    score: int  # 0-100
    checks_passed: int
    checks_failed: int
    violations: List[ValidationResult] = field(default_factory=list)
    compliance: Dict[str, bool] = field(default_factory=dict)


class MCPProtocolValidator:
    """Validates MCP server protocol compliance."""
    
    def __init__(self):
        self.violations = []
        self.compliance = {}
    
    async def validate_server(self, server_name: str, server_config: Dict) -> ProtocolReport:
        """Perform complete protocol validation on a server."""
        print(f"\n{'=' * 60}")
        print(f"MCP PROTOCOL VALIDATION: {server_name}")
        print(f"{'=' * 60}")
        
        self.violations = []
        self.compliance = {}
        
        # Start server
        process = await self._start_server(server_config)
        if not process:
            return self._generate_report(server_name, failed=True)
        
        try:
            # Run validation checks
            await self._validate_initialization(process)
            await self._validate_jsonrpc_compliance(process)
            await self._validate_required_fields(process)
            await self._validate_capabilities(process)
            await self._validate_error_handling(process)
            await self._validate_method_routing(process)
            await self._validate_response_format(process)
            await self._validate_protocol_version(process)
            
            # Terminate server
            process.terminate()
            await asyncio.wait_for(process.wait(), timeout=5)
            
        except Exception as e:
            self._add_violation(
                ValidationLevel.ERROR,
                "server_crash",
                f"Server crashed during validation: {str(e)}"
            )
        
        return self._generate_report(server_name)
    
    async def _start_server(self, server_config: Dict) -> Optional[Process]:
        """Start MCP server process."""
        try:
            cmd = server_config['command'] + server_config.get('args', [])
            
            # Set up environment
            env = None
            if 'env' in server_config:
                import os
                env = os.environ.copy()
                env.update(server_config['env'])
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            
            return process
            
        except Exception as e:
            self._add_violation(
                ValidationLevel.ERROR,
                "server_start",
                f"Failed to start server: {str(e)}"
            )
            return None
    
    async def _validate_initialization(self, process: Process):
        """Validate initialization handshake."""
        print("1. Validating initialization...")
        
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
                    "name": "mcp-protocol-validator",
                    "version": "1.0.0"
                }
            },
            "id": 1
        }
        
        response = await self._send_request(process, request)
        
        if not response:
            self._add_violation(
                ValidationLevel.ERROR,
                "init_response",
                "No response to initialize request"
            )
            return
        
        # Check response structure
        if "result" not in response:
            self._add_violation(
                ValidationLevel.ERROR,
                "init_result",
                "Initialize response missing 'result' field"
            )
        
        if "error" in response:
            self._add_violation(
                ValidationLevel.ERROR,
                "init_error",
                f"Initialize returned error: {response['error']}"
            )
        
        # Check server info
        result = response.get("result", {})
        if "serverInfo" not in result:
            self._add_violation(
                ValidationLevel.WARNING,
                "server_info",
                "Initialize response missing serverInfo"
            )
        
        if "capabilities" not in result:
            self._add_violation(
                ValidationLevel.ERROR,
                "server_capabilities",
                "Initialize response missing capabilities"
            )
        
        self.compliance["initialization"] = len([v for v in self.violations if v.check.startswith("init")]) == 0
        print(f"  └─ {'✓' if self.compliance['initialization'] else '✗'} Initialization")
    
    async def _validate_jsonrpc_compliance(self, process: Process):
        """Validate JSON-RPC 2.0 compliance."""
        print("2. Validating JSON-RPC 2.0 compliance...")
        
        # Test with various JSON-RPC scenarios
        tests = [
            # Valid request
            {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2},
            # Missing jsonrpc version
            {"method": "tools/list", "params": {}, "id": 3},
            # Wrong version
            {"jsonrpc": "1.0", "method": "tools/list", "params": {}, "id": 4},
            # Notification (no id)
            {"jsonrpc": "2.0", "method": "ping", "params": {}},
        ]
        
        for i, test in enumerate(tests):
            response = await self._send_request(process, test)
            
            if i == 0:  # Valid request
                if not response or "jsonrpc" not in response:
                    self._add_violation(
                        ValidationLevel.ERROR,
                        "jsonrpc_version",
                        "Response missing jsonrpc field"
                    )
                elif response.get("jsonrpc") != "2.0":
                    self._add_violation(
                        ValidationLevel.ERROR,
                        "jsonrpc_version",
                        f"Wrong jsonrpc version: {response.get('jsonrpc')}"
                    )
            
            elif i in [1, 2]:  # Invalid requests
                if response and "error" not in response:
                    self._add_violation(
                        ValidationLevel.WARNING,
                        "jsonrpc_validation",
                        "Server accepts invalid JSON-RPC requests"
                    )
            
            elif i == 3:  # Notification
                if response:
                    self._add_violation(
                        ValidationLevel.WARNING,
                        "jsonrpc_notification",
                        "Server responds to notifications (should be silent)"
                    )
        
        self.compliance["jsonrpc"] = len([v for v in self.violations if "jsonrpc" in v.check]) == 0
        print(f"  └─ {'✓' if self.compliance['jsonrpc'] else '✗'} JSON-RPC 2.0")
    
    async def _validate_required_fields(self, process: Process):
        """Validate required protocol fields."""
        print("3. Validating required fields...")
        
        # Test tools/list
        request = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 5}
        response = await self._send_request(process, request)
        
        if response and "result" in response:
            tools = response["result"].get("tools", [])
            if tools:
                tool = tools[0]
                required = ["name", "description", "inputSchema"]
                for field in required:
                    if field not in tool:
                        self._add_violation(
                            ValidationLevel.ERROR,
                            f"tool_{field}",
                            f"Tool missing required field: {field}"
                        )
        
        self.compliance["required_fields"] = len([v for v in self.violations if v.check.startswith("tool_")]) == 0
        print(f"  └─ {'✓' if self.compliance['required_fields'] else '✗'} Required fields")
    
    async def _validate_capabilities(self, process: Process):
        """Validate capability declarations match implementation."""
        print("4. Validating capabilities...")
        
        # Get declared capabilities from initialization
        init_request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "1.0.0",
                "capabilities": {"tools": True},
                "clientInfo": {"name": "validator", "version": "1.0"}
            },
            "id": 6
        }
        
        init_response = await self._send_request(process, init_request)
        if not init_response or "result" not in init_response:
            return
        
        declared_caps = init_response["result"].get("capabilities", {})
        
        # Test each declared capability
        if declared_caps.get("tools"):
            test = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 7}
            response = await self._send_request(process, test)
            if not response or "error" in response:
                self._add_violation(
                    ValidationLevel.ERROR,
                    "capability_tools",
                    "Declared tools capability but tools/list fails"
                )
        
        if declared_caps.get("resources"):
            test = {"jsonrpc": "2.0", "method": "resources/list", "params": {}, "id": 8}
            response = await self._send_request(process, test)
            if not response or "error" in response:
                self._add_violation(
                    ValidationLevel.WARNING,
                    "capability_resources",
                    "Declared resources capability but resources/list fails"
                )
        
        self.compliance["capabilities"] = len([v for v in self.violations if "capability" in v.check]) == 0
        print(f"  └─ {'✓' if self.compliance['capabilities'] else '✗'} Capabilities")
    
    async def _validate_error_handling(self, process: Process):
        """Validate proper error handling."""
        print("5. Validating error handling...")
        
        # Test various error scenarios
        error_tests = [
            # Unknown method
            {"jsonrpc": "2.0", "method": "invalid/method", "params": {}, "id": 9},
            # Invalid params
            {"jsonrpc": "2.0", "method": "tools/call", "params": {"invalid": "params"}, "id": 10},
            # Malformed JSON (will be caught before sending)
        ]
        
        for test in error_tests:
            response = await self._send_request(process, test)
            
            if response and "error" in response:
                error = response["error"]
                # Check error structure
                if "code" not in error:
                    self._add_violation(
                        ValidationLevel.ERROR,
                        "error_code",
                        "Error response missing 'code' field"
                    )
                if "message" not in error:
                    self._add_violation(
                        ValidationLevel.ERROR,
                        "error_message",
                        "Error response missing 'message' field"
                    )
            elif response:
                self._add_violation(
                    ValidationLevel.ERROR,
                    "error_missing",
                    "Invalid request did not return error"
                )
        
        self.compliance["error_handling"] = len([v for v in self.violations if "error" in v.check]) <= 2
        print(f"  └─ {'✓' if self.compliance['error_handling'] else '✗'} Error handling")
    
    async def _validate_method_routing(self, process: Process):
        """Validate method routing and namespacing."""
        print("6. Validating method routing...")
        
        # Standard MCP methods
        standard_methods = [
            "initialize",
            "tools/list",
            "resources/list",
            "prompts/list"
        ]
        
        for method in standard_methods:
            if method == "initialize":
                continue  # Already tested
            
            request = {"jsonrpc": "2.0", "method": method, "params": {}, "id": 20 + standard_methods.index(method)}
            response = await self._send_request(process, request)
            
            if not response:
                self._add_violation(
                    ValidationLevel.WARNING,
                    f"method_{method.replace('/', '_')}",
                    f"No response to {method} request"
                )
        
        self.compliance["method_routing"] = len([v for v in self.violations if v.check.startswith("method_")]) == 0
        print(f"  └─ {'✓' if self.compliance['method_routing'] else '✗'} Method routing")
    
    async def _validate_response_format(self, process: Process):
        """Validate response format consistency."""
        print("7. Validating response format...")
        
        request = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 30}
        response = await self._send_request(process, request)
        
        if response:
            # Check ID matches
            if response.get("id") != request["id"]:
                self._add_violation(
                    ValidationLevel.ERROR,
                    "response_id",
                    f"Response ID {response.get('id')} doesn't match request ID {request['id']}"
                )
            
            # Check mutually exclusive result/error
            if "result" in response and "error" in response:
                self._add_violation(
                    ValidationLevel.ERROR,
                    "response_exclusive",
                    "Response contains both 'result' and 'error' (must be exclusive)"
                )
        
        self.compliance["response_format"] = len([v for v in self.violations if "response" in v.check]) == 0
        print(f"  └─ {'✓' if self.compliance['response_format'] else '✗'} Response format")
    
    async def _validate_protocol_version(self, process: Process):
        """Validate protocol version handling."""
        print("8. Validating protocol version...")
        
        # Test with different protocol versions
        versions = ["0.1.0", "1.0.0", "2.0.0", "999.0.0"]
        
        for version in versions:
            request = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": version,
                    "capabilities": {},
                    "clientInfo": {"name": "validator", "version": "1.0"}
                },
                "id": 40 + versions.index(version)
            }
            
            response = await self._send_request(process, request)
            
            if version == "999.0.0" and response and "error" not in response:
                self._add_violation(
                    ValidationLevel.WARNING,
                    "version_future",
                    "Server accepts far-future protocol version"
                )
        
        self.compliance["protocol_version"] = True  # Informational only
        print(f"  └─ {'✓' if self.compliance['protocol_version'] else '✗'} Protocol version")
    
    async def _send_request(self, process: Process, request: Dict) -> Optional[Dict]:
        """Send request and receive response."""
        try:
            # Send request
            request_str = json.dumps(request) + "\n"
            process.stdin.write(request_str.encode())
            await process.stdin.drain()
            
            # Read response with timeout
            try:
                response_line = await asyncio.wait_for(
                    process.stdout.readline(),
                    timeout=2.0
                )
            except asyncio.TimeoutError:
                return None
            
            if not response_line:
                return None
            
            return json.loads(response_line.decode())
            
        except Exception as e:
            return None
    
    def _add_violation(self, level: ValidationLevel, check: str, message: str, details: Dict = None):
        """Add a validation violation."""
        self.violations.append(ValidationResult(level, check, message, details))
    
    def _generate_report(self, server_name: str, failed: bool = False) -> ProtocolReport:
        """Generate validation report."""
        if failed:
            return ProtocolReport(
                server_name=server_name,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                passed=False,
                score=0,
                checks_passed=0,
                checks_failed=1,
                violations=[ValidationResult(
                    ValidationLevel.ERROR,
                    "server_start",
                    "Failed to start server"
                )],
                compliance={}
            )
        
        # Calculate score
        errors = len([v for v in self.violations if v.level == ValidationLevel.ERROR])
        warnings = len([v for v in self.violations if v.level == ValidationLevel.WARNING])
        
        score = max(0, 100 - (errors * 20) - (warnings * 5))
        passed = errors == 0
        
        checks_passed = len([k for k, v in self.compliance.items() if v])
        checks_failed = len(self.compliance) - checks_passed
        
        return ProtocolReport(
            server_name=server_name,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            passed=passed,
            score=score,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            violations=self.violations,
            compliance=self.compliance
        )


def print_report(report: ProtocolReport):
    """Print formatted validation report."""
    print("\n" + "=" * 60)
    print("PROTOCOL VALIDATION REPORT")
    print("=" * 60)
    print(f"Server: {report.server_name}")
    print(f"Time: {report.timestamp}")
    print(f"Score: {report.score}/100")
    print(f"Status: {'PASSED' if report.passed else 'FAILED'}")
    print(f"Checks: {report.checks_passed} passed, {report.checks_failed} failed")
    
    if report.violations:
        print("\nVIOLATIONS:")
        
        errors = [v for v in report.violations if v.level == ValidationLevel.ERROR]
        warnings = [v for v in report.violations if v.level == ValidationLevel.WARNING]
        
        if errors:
            print("\n  ERRORS:")
            for v in errors:
                print(f"    ✗ {v.check}: {v.message}")
        
        if warnings:
            print("\n  WARNINGS:")
            for v in warnings:
                print(f"    ⚠ {v.check}: {v.message}")
    
    print("\nCOMPLIANCE:")
    for check, passed in report.compliance.items():
        symbol = "✓" if passed else "✗"
        print(f"  {symbol} {check.replace('_', ' ').title()}")
    
    print("\n" + "=" * 60)


async def main():
    """Run protocol validation."""
    from config import SERVERS
    
    validator = MCPProtocolValidator()
    
    # Test filesystem server
    report = await validator.validate_server("filesystem", SERVERS["filesystem"])
    print_report(report)
    
    # Save report
    with open(f"protocol_report_{report.server_name}.json", "w") as f:
        json.dump({
            "server": report.server_name,
            "timestamp": report.timestamp,
            "score": report.score,
            "passed": report.passed,
            "compliance": report.compliance,
            "violations": [
                {
                    "level": v.level.value,
                    "check": v.check,
                    "message": v.message
                }
                for v in report.violations
            ]
        }, f, indent=2)
    
    print(f"\nReport saved to protocol_report_{report.server_name}.json")
    
    return 0 if report.passed else 1


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)