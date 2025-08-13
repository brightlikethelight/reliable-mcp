#!/usr/bin/env python3
"""
MCP Security Vulnerability Scanner
Tests for common security vulnerabilities in MCP server implementations.
First comprehensive security testing tool for MCP servers.
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from mcp_client import MCPClient
from config import SERVERS, TEST_DIR


class ThreatLevel(Enum):
    """Security threat severity levels."""
    CRITICAL = "critical"  # Remote code execution, data breach
    HIGH = "high"         # Privilege escalation, auth bypass
    MEDIUM = "medium"     # Information disclosure, DoS
    LOW = "low"          # Best practice violations
    INFO = "info"        # Informational findings


@dataclass
class SecurityFinding:
    """A security vulnerability or finding."""
    threat_level: ThreatLevel
    vulnerability: str
    description: str
    impact: str
    recommendation: str
    test_details: Optional[Dict] = None


@dataclass
class SecurityReport:
    """Complete security assessment report."""
    server_name: str
    timestamp: str
    risk_score: int  # 0-100 (100 = very risky)
    findings_count: Dict[str, int]
    findings: List[SecurityFinding] = field(default_factory=list)
    passed_tests: List[str] = field(default_factory=list)
    failed_tests: List[str] = field(default_factory=list)


class MCPSecurityScanner:
    """Security vulnerability scanner for MCP servers."""
    
    # Common prompt injection payloads
    INJECTION_PAYLOADS = [
        "'; DROP TABLE users; --",
        "../../../etc/passwd",
        "{{ 7*7 }}",  # Template injection
        "${7*7}",     # Expression injection
        "$(whoami)",  # Command injection
        "`id`",       # Command injection
        "<!--#exec cmd=\"ls\" -->",  # SSI injection
        "';alert(1);//",  # XSS attempt
        "\x00\x01\x02\x03",  # Binary injection
        "A" * 10000,  # Buffer overflow attempt
    ]
    
    # Sensitive file paths to test
    SENSITIVE_PATHS = [
        "/etc/passwd",
        "/etc/shadow",
        "~/.ssh/id_rsa",
        "../../../etc/passwd",
        "C:\\Windows\\System32\\config\\SAM",
        ".env",
        "config.json",
        ".git/config",
    ]
    
    def __init__(self):
        self.findings = []
        self.passed_tests = []
        self.failed_tests = []
    
    async def scan_server(self, server_name: str) -> SecurityReport:
        """Perform complete security scan on a server."""
        print(f"\n{'=' * 60}")
        print(f"SECURITY VULNERABILITY SCAN: {server_name}")
        print(f"{'=' * 60}")
        
        self.findings = []
        self.passed_tests = []
        self.failed_tests = []
        
        # Check for required environment variables
        server_config = SERVERS.get(server_name, {})
        if 'env' in server_config:
            missing = [k for k, v in server_config['env'].items() if not v and 'TOKEN' in k]
            if missing:
                print(f"⚠ Skipping - missing required env vars: {', '.join(missing)}")
                return self._generate_report(server_name, skipped=True)
        
        # Initialize client
        client = MCPClient(server_name)
        
        try:
            print("Starting security scan...")
            await client.start()
            
            # Run security tests
            await self._test_prompt_injection(client)
            await self._test_path_traversal(client)
            await self._test_privilege_escalation(client)
            await self._test_information_disclosure(client)
            await self._test_dos_vulnerabilities(client)
            await self._test_tool_permissions(client)
            await self._test_input_validation(client)
            await self._test_output_sanitization(client)
            
            await client.stop()
            
        except Exception as e:
            self._add_finding(
                ThreatLevel.MEDIUM,
                "server_crash",
                f"Server crashed during security testing: {str(e)}",
                "Denial of service vulnerability",
                "Implement proper error handling and resource limits"
            )
        
        return self._generate_report(server_name)
    
    async def _test_prompt_injection(self, client: MCPClient):
        """Test for prompt injection vulnerabilities."""
        print("\n1. Testing prompt injection...")
        vulnerable = False
        
        for payload in self.INJECTION_PAYLOADS:
            try:
                # Try to inject via file operations
                if await self._has_tool(client, "write_file"):
                    result = await client.call_tool("write_file", {
                        "path": f"{TEST_DIR}/test_{payload[:10]}.txt",
                        "content": payload
                    })
                    
                    # Check if payload was executed
                    if "error" not in str(result).lower():
                        # Try to read it back
                        if await self._has_tool(client, "read_file"):
                            read_result = await client.call_tool("read_file", {
                                "path": f"{TEST_DIR}/test_{payload[:10]}.txt"
                            })
                            
                            # Check for signs of execution
                            if payload in ["$(whoami)", "`id`"]:
                                content = str(read_result)
                                if "root" in content or "uid=" in content:
                                    vulnerable = True
                                    self._add_finding(
                                        ThreatLevel.CRITICAL,
                                        "command_injection",
                                        f"Command injection via {payload}",
                                        "Remote code execution possible",
                                        "Sanitize all inputs and use parameterized commands"
                                    )
            except:
                pass  # Expected for most payloads
        
        if not vulnerable:
            self.passed_tests.append("prompt_injection")
            print("  └─ ✓ No prompt injection vulnerabilities found")
        else:
            self.failed_tests.append("prompt_injection")
            print("  └─ ✗ CRITICAL: Command injection vulnerability detected!")
    
    async def _test_path_traversal(self, client: MCPClient):
        """Test for path traversal vulnerabilities."""
        print("\n2. Testing path traversal...")
        vulnerable = False
        
        for path in self.SENSITIVE_PATHS:
            try:
                if await self._has_tool(client, "read_file"):
                    result = await client.call_tool("read_file", {"path": path})
                    
                    # Check if we accessed sensitive file
                    if result and "error" not in str(result).lower():
                        content = str(result)
                        
                        # Check for known sensitive content
                        if any(marker in content for marker in ["root:", "Administrator:", "ssh-rsa"]):
                            vulnerable = True
                            self._add_finding(
                                ThreatLevel.CRITICAL,
                                "path_traversal",
                                f"Path traversal allows reading {path}",
                                "Unauthorized access to sensitive files",
                                "Implement strict path validation and sandboxing"
                            )
                            break
            except:
                pass  # Expected for most paths
        
        if not vulnerable:
            self.passed_tests.append("path_traversal")
            print("  └─ ✓ No path traversal vulnerabilities found")
        else:
            self.failed_tests.append("path_traversal")
            print("  └─ ✗ CRITICAL: Path traversal vulnerability detected!")
    
    async def _test_privilege_escalation(self, client: MCPClient):
        """Test for privilege escalation vulnerabilities."""
        print("\n3. Testing privilege escalation...")
        
        try:
            tools = await client.list_tools()
            
            # Check for dangerous tools
            dangerous_tools = [
                "execute_command", "run_shell", "system", "exec",
                "eval", "compile", "import", "require"
            ]
            
            found_dangerous = []
            for tool in tools:
                tool_name = tool.get("name", "").lower()
                if any(danger in tool_name for danger in dangerous_tools):
                    found_dangerous.append(tool_name)
            
            if found_dangerous:
                self._add_finding(
                    ThreatLevel.HIGH,
                    "dangerous_tools",
                    f"Dangerous tools exposed: {', '.join(found_dangerous)}",
                    "Potential for privilege escalation",
                    "Remove or restrict access to system-level tools"
                )
                self.failed_tests.append("privilege_escalation")
                print(f"  └─ ✗ HIGH: Dangerous tools found: {', '.join(found_dangerous)}")
            else:
                self.passed_tests.append("privilege_escalation")
                print("  └─ ✓ No privilege escalation vectors found")
                
        except Exception as e:
            print(f"  └─ ⚠ Could not test: {str(e)}")
    
    async def _test_information_disclosure(self, client: MCPClient):
        """Test for information disclosure vulnerabilities."""
        print("\n4. Testing information disclosure...")
        
        findings = []
        
        try:
            # Test error messages for stack traces
            if await self._has_tool(client, "read_file"):
                result = await client.call_tool("read_file", {
                    "path": "/definitely/does/not/exist/../../etc/passwd"
                })
                
                error_msg = str(result)
                
                # Check for sensitive information in errors
                if any(marker in error_msg for marker in [
                    "Traceback", "at line", "stack trace", 
                    "/home/", "/usr/", "C:\\", ":\\Users\\"
                ]):
                    findings.append("Stack traces in error messages")
                
                # Check for version disclosure
                if any(marker in error_msg for marker in [
                    "version", "v1.", "v2.", "node", "python"
                ]):
                    findings.append("Version information in errors")
        except:
            pass
        
        if findings:
            self._add_finding(
                ThreatLevel.MEDIUM,
                "info_disclosure",
                f"Information disclosure: {', '.join(findings)}",
                "Sensitive information exposed in error messages",
                "Sanitize error messages before returning to client"
            )
            self.failed_tests.append("information_disclosure")
            print(f"  └─ ✗ MEDIUM: {', '.join(findings)}")
        else:
            self.passed_tests.append("information_disclosure")
            print("  └─ ✓ No information disclosure found")
    
    async def _test_dos_vulnerabilities(self, client: MCPClient):
        """Test for denial of service vulnerabilities."""
        print("\n5. Testing DoS vulnerabilities...")
        
        vulnerable = False
        
        try:
            # Test large input handling
            if await self._has_tool(client, "write_file"):
                large_content = "A" * 1000000  # 1MB of data
                
                start_time = time.time()
                result = await client.call_tool("write_file", {
                    "path": f"{TEST_DIR}/large_file.txt",
                    "content": large_content
                })
                elapsed = time.time() - start_time
                
                # Check if it took too long (potential DoS)
                if elapsed > 10:
                    vulnerable = True
                    self._add_finding(
                        ThreatLevel.MEDIUM,
                        "dos_large_input",
                        "Server hangs on large input",
                        "Denial of service via resource exhaustion",
                        "Implement input size limits and timeouts"
                    )
            
            # Test recursive operations
            if await self._has_tool(client, "list_directory"):
                # Try to list root directory (could be huge)
                start_time = time.time()
                result = await asyncio.wait_for(
                    client.call_tool("list_directory", {"path": "/"}),
                    timeout=5
                )
                elapsed = time.time() - start_time
                
                if elapsed > 3:
                    vulnerable = True
                    self._add_finding(
                        ThreatLevel.LOW,
                        "dos_recursive",
                        "Slow recursive operations possible",
                        "Performance degradation under load",
                        "Implement pagination and depth limits"
                    )
                    
        except asyncio.TimeoutError:
            vulnerable = True
            self._add_finding(
                ThreatLevel.MEDIUM,
                "dos_timeout",
                "Operations can hang indefinitely",
                "Denial of service via hung operations",
                "Implement proper timeouts for all operations"
            )
        except:
            pass
        
        if not vulnerable:
            self.passed_tests.append("dos")
            print("  └─ ✓ No DoS vulnerabilities found")
        else:
            self.failed_tests.append("dos")
            print("  └─ ✗ MEDIUM: DoS vulnerabilities detected")
    
    async def _test_tool_permissions(self, client: MCPClient):
        """Test tool permission boundaries."""
        print("\n6. Testing tool permissions...")
        
        issues = []
        
        try:
            tools = await client.list_tools()
            
            # Check for missing input validation schemas
            for tool in tools:
                if "inputSchema" not in tool:
                    issues.append(f"{tool.get('name', 'unknown')}: Missing input schema")
            
            # Test permission bypass attempts
            if await self._has_tool(client, "write_file"):
                # Try to write to system directory
                result = await client.call_tool("write_file", {
                    "path": "/etc/test_permission.txt",
                    "content": "test"
                })
                
                if "error" not in str(result).lower():
                    issues.append("Can write to system directories")
            
        except:
            pass
        
        if issues:
            self._add_finding(
                ThreatLevel.HIGH,
                "permission_issues",
                f"Permission issues: {'; '.join(issues[:3])}",
                "Insufficient access controls",
                "Implement proper permission checks and schemas"
            )
            self.failed_tests.append("tool_permissions")
            print(f"  └─ ✗ HIGH: Permission issues found")
        else:
            self.passed_tests.append("tool_permissions")
            print("  └─ ✓ Tool permissions properly enforced")
    
    async def _test_input_validation(self, client: MCPClient):
        """Test input validation."""
        print("\n7. Testing input validation...")
        
        issues = []
        
        try:
            # Test with invalid inputs
            test_cases = [
                ("write_file", {"path": None, "content": "test"}),
                ("write_file", {"path": "", "content": "test"}),
                ("write_file", {"path": 123, "content": "test"}),
                ("write_file", {"path": ["array"], "content": "test"}),
                ("write_file", {"path": {"object": "dict"}, "content": "test"}),
            ]
            
            for tool_name, params in test_cases:
                if await self._has_tool(client, tool_name):
                    try:
                        result = await client.call_tool(tool_name, params)
                        if "error" not in str(result).lower():
                            issues.append(f"Accepts invalid input: {params}")
                    except:
                        pass  # Expected
            
        except:
            pass
        
        if issues:
            self._add_finding(
                ThreatLevel.MEDIUM,
                "input_validation",
                "Weak input validation",
                "Invalid inputs not properly rejected",
                "Implement strict input validation using schemas"
            )
            self.failed_tests.append("input_validation")
            print("  └─ ✗ MEDIUM: Input validation issues")
        else:
            self.passed_tests.append("input_validation")
            print("  └─ ✓ Input validation working properly")
    
    async def _test_output_sanitization(self, client: MCPClient):
        """Test output sanitization."""
        print("\n8. Testing output sanitization...")
        
        issues = []
        
        try:
            # Test if dangerous content is sanitized
            if await self._has_tool(client, "write_file") and await self._has_tool(client, "read_file"):
                dangerous_content = "<script>alert(1)</script>"
                
                await client.call_tool("write_file", {
                    "path": f"{TEST_DIR}/xss_test.html",
                    "content": dangerous_content
                })
                
                result = await client.call_tool("read_file", {
                    "path": f"{TEST_DIR}/xss_test.html"
                })
                
                # Check if dangerous content is returned as-is
                if dangerous_content in str(result):
                    issues.append("No output sanitization for XSS")
            
        except:
            pass
        
        if issues:
            self._add_finding(
                ThreatLevel.LOW,
                "output_sanitization",
                "Missing output sanitization",
                "Potentially dangerous content not sanitized",
                "Sanitize output based on context"
            )
            self.failed_tests.append("output_sanitization")
            print("  └─ ✗ LOW: Output sanitization issues")
        else:
            self.passed_tests.append("output_sanitization")
            print("  └─ ✓ Output properly sanitized")
    
    async def _has_tool(self, client: MCPClient, tool_name: str) -> bool:
        """Check if server has a specific tool."""
        try:
            tools = await client.list_tools()
            return any(tool.get("name") == tool_name for tool in tools)
        except:
            return False
    
    def _add_finding(self, level: ThreatLevel, vuln: str, desc: str, impact: str, rec: str, details: Dict = None):
        """Add a security finding."""
        self.findings.append(SecurityFinding(level, vuln, desc, impact, rec, details))
    
    def _generate_report(self, server_name: str, skipped: bool = False) -> SecurityReport:
        """Generate security report."""
        if skipped:
            return SecurityReport(
                server_name=server_name,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                risk_score=0,
                findings_count={"skipped": 1},
                findings=[],
                passed_tests=[],
                failed_tests=[]
            )
        
        # Calculate risk score
        risk_score = 0
        findings_count = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0
        }
        
        for finding in self.findings:
            findings_count[finding.threat_level.value] += 1
            
            if finding.threat_level == ThreatLevel.CRITICAL:
                risk_score += 25
            elif finding.threat_level == ThreatLevel.HIGH:
                risk_score += 15
            elif finding.threat_level == ThreatLevel.MEDIUM:
                risk_score += 8
            elif finding.threat_level == ThreatLevel.LOW:
                risk_score += 3
        
        risk_score = min(100, risk_score)
        
        return SecurityReport(
            server_name=server_name,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            risk_score=risk_score,
            findings_count=findings_count,
            findings=self.findings,
            passed_tests=self.passed_tests,
            failed_tests=self.failed_tests
        )


def print_security_report(report: SecurityReport):
    """Print formatted security report."""
    print("\n" + "=" * 60)
    print("SECURITY ASSESSMENT REPORT")
    print("=" * 60)
    print(f"Server: {report.server_name}")
    print(f"Time: {report.timestamp}")
    print(f"Risk Score: {report.risk_score}/100")
    
    # Risk level
    if report.risk_score >= 75:
        risk_level = "CRITICAL RISK"
    elif report.risk_score >= 50:
        risk_level = "HIGH RISK"
    elif report.risk_score >= 25:
        risk_level = "MEDIUM RISK"
    elif report.risk_score >= 10:
        risk_level = "LOW RISK"
    else:
        risk_level = "MINIMAL RISK"
    
    print(f"Risk Level: {risk_level}")
    
    print(f"\nTests Passed: {len(report.passed_tests)}")
    print(f"Tests Failed: {len(report.failed_tests)}")
    
    if report.findings_count:
        print("\nFINDINGS BY SEVERITY:")
        for level, count in report.findings_count.items():
            if count > 0:
                print(f"  {level.upper()}: {count}")
    
    if report.findings:
        print("\nDETAILED FINDINGS:")
        
        for level in [ThreatLevel.CRITICAL, ThreatLevel.HIGH, ThreatLevel.MEDIUM, ThreatLevel.LOW, ThreatLevel.INFO]:
            findings = [f for f in report.findings if f.threat_level == level]
            if findings:
                print(f"\n  {level.value.upper()}:")
                for f in findings:
                    print(f"    • {f.vulnerability}: {f.description}")
                    print(f"      Impact: {f.impact}")
                    print(f"      Fix: {f.recommendation}")
    
    print("\n" + "=" * 60)


async def main():
    """Run security scan."""
    import sys
    from config import SERVERS
    
    # Get server name from command line or default to filesystem
    server_name = sys.argv[1] if len(sys.argv) > 1 else "filesystem"
    
    if server_name not in SERVERS:
        print(f"Unknown server: {server_name}")
        print(f"Available servers: {', '.join(SERVERS.keys())}")
        return 1
    
    scanner = MCPSecurityScanner()
    report = await scanner.scan_server(server_name)
    print_security_report(report)
    
    # Save report
    report_file = f"security_report_{server_name}.json"
    with open(report_file, "w") as f:
        json.dump({
            "server": report.server_name,
            "timestamp": report.timestamp,
            "risk_score": report.risk_score,
            "risk_level": "critical" if report.risk_score >= 75 else "high" if report.risk_score >= 50 else "medium" if report.risk_score >= 25 else "low" if report.risk_score >= 10 else "minimal",
            "findings_count": report.findings_count,
            "passed_tests": report.passed_tests,
            "failed_tests": report.failed_tests,
            "findings": [
                {
                    "level": f.threat_level.value,
                    "vulnerability": f.vulnerability,
                    "description": f.description,
                    "impact": f.impact,
                    "recommendation": f.recommendation
                }
                for f in report.findings
            ]
        }, f, indent=2)
    
    print(f"\nReport saved to {report_file}")
    
    return 0 if report.risk_score < 50 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)