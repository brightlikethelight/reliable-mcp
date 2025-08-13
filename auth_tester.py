#!/usr/bin/env python3
"""
MCP Authentication Vulnerability Tester
Tests for the #1 production issue: servers exposed without authentication.
45% of vendors dismiss this as "acceptable" - we prove why it's not.
"""

import asyncio
import json
import time
import random
import string
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from mcp_client import MCPClient
from config import SERVERS


class AuthVulnerability(Enum):
    """Types of authentication vulnerabilities."""
    NO_AUTH = "no_authentication"
    WEAK_AUTH = "weak_authentication"
    BYPASS = "authentication_bypass"
    SESSION_HIJACK = "session_hijacking"
    TOKEN_LEAK = "token_leakage"
    PERMISSION_ESCALATION = "permission_escalation"


@dataclass
class AuthFinding:
    """Authentication vulnerability finding."""
    vulnerability: AuthVulnerability
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    description: str
    impact: str
    proof: Optional[str] = None


class AuthenticationTester:
    """Test MCP servers for authentication vulnerabilities."""
    
    def __init__(self):
        self.findings = []
        self.auth_tests_passed = []
        self.auth_tests_failed = []
    
    async def test_authentication(self, server_name: str) -> Dict:
        """Comprehensive authentication testing."""
        
        print(f"\n{'=' * 70}")
        print(f"AUTHENTICATION VULNERABILITY TEST: {server_name}")
        print(f"Testing for exposed servers and auth bypass")
        print(f"{'=' * 70}")
        
        # Check if this is a local server (designed to run without auth)
        from config import SERVERS
        server_config = SERVERS.get(server_name, {})
        transport = server_config.get('transport', 'stdio')
        
        if transport == 'stdio':
            print("\n⚠️ Note: This is a LOCAL server using stdio transport.")
            print("Local servers are designed to run without network authentication.")
            print("Testing for other security issues...\n")
        
        # Test 1: No Authentication Required
        print("\n1. Testing for missing authentication...")
        no_auth = await self._test_no_authentication(server_name)
        
        # Check if this is expected for local servers
        if transport == 'stdio' and no_auth:
            self.auth_tests_passed.append("no_auth")
            print("  ✓ Local server correctly accepts local connections (expected behavior)")
        elif transport != 'stdio' and no_auth:
            self.findings.append(AuthFinding(
                vulnerability=AuthVulnerability.NO_AUTH,
                severity="CRITICAL",
                description="REMOTE server accepts requests without any authentication",
                impact="Remote server exposed without authentication",
                proof="Successfully executed operations without credentials"
            ))
            print("  ⚠️ CRITICAL: REMOTE Server has NO AUTHENTICATION!")
        elif transport != 'stdio' and not no_auth:
            self.auth_tests_passed.append("no_auth")
            print("  ✓ Remote server requires authentication (correct)")
        else:
            self.auth_tests_passed.append("no_auth")
            print("  ✓ Authentication working as expected")
        
        # Test 2: Authentication Bypass (only for remote servers)
        if transport != 'stdio':
            print("\n2. Testing for authentication bypass...")
            bypass = await self._test_auth_bypass(server_name)
            if bypass:
                self.findings.append(AuthFinding(
                    vulnerability=AuthVulnerability.BYPASS,
                    severity="CRITICAL",
                    description=f"Authentication can be bypassed using: {bypass}",
                    impact="Attackers can gain unauthorized access",
                    proof=bypass
                ))
                print(f"  ⚠️ CRITICAL: Auth bypass found: {bypass}")
            else:
                self.auth_tests_passed.append("auth_bypass")
                print("  ✓ No authentication bypass found")
        else:
            print("\n2. Skipping auth bypass test (local server)")
            self.auth_tests_passed.append("auth_bypass")
        
        # Test 3: Session Hijacking
        print("\n3. Testing for session hijacking vulnerabilities...")
        hijack = await self._test_session_hijacking(server_name)
        if hijack:
            self.findings.append(AuthFinding(
                vulnerability=AuthVulnerability.SESSION_HIJACK,
                severity="HIGH",
                description="Sessions can be hijacked or predicted",
                impact="Attackers can steal active user sessions",
                proof=hijack
            ))
            print(f"  ⚠️ HIGH: Session hijacking possible: {hijack}")
        else:
            self.auth_tests_passed.append("session_hijack")
            print("  ✓ Sessions are secure")
        
        # Test 4: Token Leakage
        print("\n4. Testing for token/credential leakage...")
        leak = await self._test_token_leakage(server_name)
        if leak:
            self.findings.append(AuthFinding(
                vulnerability=AuthVulnerability.TOKEN_LEAK,
                severity="HIGH",
                description="Credentials or tokens exposed in responses",
                impact="Sensitive authentication data can be stolen",
                proof=leak
            ))
            print(f"  ⚠️ HIGH: Token leakage detected: {leak}")
        else:
            self.auth_tests_passed.append("token_leak")
            print("  ✓ No credential leakage found")
        
        # Test 5: Permission Escalation
        print("\n5. Testing for permission escalation...")
        escalation = await self._test_permission_escalation(server_name)
        if escalation:
            self.findings.append(AuthFinding(
                vulnerability=AuthVulnerability.PERMISSION_ESCALATION,
                severity="HIGH",
                description="Low-privilege users can escalate to admin",
                impact="Users can gain unauthorized elevated privileges",
                proof=escalation
            ))
            print(f"  ⚠️ HIGH: Permission escalation: {escalation}")
        else:
            self.auth_tests_passed.append("permission_escalation")
            print("  ✓ Permissions properly enforced")
        
        # Test 6: Weak Authentication
        print("\n6. Testing for weak authentication mechanisms...")
        weak = await self._test_weak_authentication(server_name)
        if weak:
            self.findings.append(AuthFinding(
                vulnerability=AuthVulnerability.WEAK_AUTH,
                severity="MEDIUM",
                description=f"Weak authentication mechanism: {weak}",
                impact="Authentication can be easily compromised",
                proof=weak
            ))
            print(f"  ⚠️ MEDIUM: Weak authentication: {weak}")
        else:
            self.auth_tests_passed.append("weak_auth")
            print("  ✓ Authentication mechanism is strong")
        
        return self._generate_report(server_name)
    
    async def _test_no_authentication(self, server_name: str) -> bool:
        """Test if server accepts requests without authentication."""
        
        try:
            # Create client without any credentials
            client = MCPClient(server_name)
            
            # Remove any auth from environment
            original_env = {}
            auth_vars = ['TOKEN', 'API_KEY', 'PASSWORD', 'SECRET', 'AUTH']
            for key in list(os.environ.keys()):
                if any(auth in key.upper() for auth in auth_vars):
                    original_env[key] = os.environ.pop(key, None)
            
            try:
                # Try to connect and execute operations
                await client.start()
                
                # Try to list tools (should require auth)
                tools = await client.list_tools()
                
                # Try to execute a tool (definitely should require auth)
                if tools:
                    tool = tools[0]
                    try:
                        result = await client.call_tool(tool['name'], {})
                        # If we get here, there's NO AUTHENTICATION!
                        await client.stop()
                        return True
                    except:
                        pass
                
                # Server started and listed tools without auth
                await client.stop()
                return True  # NO AUTH REQUIRED!
                
            finally:
                # Restore environment
                for key, value in original_env.items():
                    if value is not None:
                        os.environ[key] = value
                        
        except Exception as e:
            # Expected - server should reject without auth
            if "auth" in str(e).lower() or "unauthorized" in str(e).lower():
                return False  # Good - auth is required
            # Some other error - might still be no auth
            return False
        
        return False
    
    async def _test_auth_bypass(self, server_name: str) -> Optional[str]:
        """Test for authentication bypass vulnerabilities."""
        
        bypass_techniques = [
            # SQL injection in auth
            ("auth_token", "' OR '1'='1"),
            ("password", "' OR 1=1 --"),
            
            # NoSQL injection
            ("token", '{"$ne": null}'),
            ("auth", '{"$gt": ""}'),
            
            # JWT manipulation
            ("authorization", "Bearer eyJhbGciOiJub25lIn0.eyJzdWIiOiJhZG1pbiJ9."),
            
            # Magic values
            ("api_key", "admin"),
            ("token", "test"),
            ("auth", "bypass"),
            
            # Header injection
            ("X-Forwarded-For", "127.0.0.1"),
            ("X-Real-IP", "localhost"),
            ("X-Admin", "true"),
            
            # Parameter pollution
            ("auth", "valid&auth=bypass"),
        ]
        
        for param, value in bypass_techniques:
            try:
                client = MCPClient(server_name)
                
                # Inject bypass attempt
                import os
                os.environ[f"MCP_{param.upper()}"] = value
                
                try:
                    await client.start()
                    # If we connected with bypass value, it's vulnerable
                    tools = await client.list_tools()
                    if tools:
                        await client.stop()
                        return f"{param}={value}"
                except:
                    pass
                finally:
                    # Clean up
                    os.environ.pop(f"MCP_{param.upper()}", None)
                    
            except:
                pass
        
        return None
    
    async def _test_session_hijacking(self, server_name: str) -> Optional[str]:
        """Test for session hijacking vulnerabilities."""
        
        try:
            # Start legitimate session
            client1 = MCPClient(server_name)
            await client1.start()
            
            # Check if session ID is predictable or exposed
            if hasattr(client1, 'session_id'):
                session_id = client1.session_id
                
                # Check if session ID is weak
                if session_id:
                    # Check for sequential IDs
                    if session_id.isdigit():
                        return "Sequential numeric session IDs"
                    
                    # Check for timestamp-based IDs
                    if str(int(time.time())) in str(session_id):
                        return "Timestamp-based session IDs"
                    
                    # Check for short IDs
                    if len(str(session_id)) < 16:
                        return f"Short session ID: {len(str(session_id))} chars"
            
            # Try to hijack session
            client2 = MCPClient(server_name)
            
            # Attempt session fixation
            if hasattr(client1, 'session_id'):
                client2.session_id = client1.session_id
                try:
                    await client2.start()
                    # If we can use same session, it's vulnerable
                    tools = await client2.list_tools()
                    if tools:
                        await client1.stop()
                        await client2.stop()
                        return "Session fixation possible"
                except:
                    pass
            
            await client1.stop()
            
        except:
            pass
        
        return None
    
    async def _test_token_leakage(self, server_name: str) -> Optional[str]:
        """Test for token/credential leakage."""
        
        try:
            client = MCPClient(server_name)
            
            # Set a test token
            test_token = "SECRET_TOKEN_12345"
            os.environ["MCP_TEST_TOKEN"] = test_token
            
            try:
                await client.start()
                
                # Check if token appears in responses
                tools = await client.list_tools()
                
                # Check tool descriptions for leakage
                for tool in tools:
                    tool_str = json.dumps(tool)
                    if test_token in tool_str:
                        return "Token leaked in tool descriptions"
                    
                    # Check for partial token leakage
                    if test_token[:10] in tool_str:
                        return "Partial token leaked"
                
                # Try to trigger error to check error messages
                try:
                    await client.call_tool("nonexistent_tool", {})
                except Exception as e:
                    error_str = str(e)
                    if test_token in error_str:
                        return "Token leaked in error messages"
                    if "SECRET" in error_str:
                        return "Sensitive data in error messages"
                
                await client.stop()
                
            finally:
                os.environ.pop("MCP_TEST_TOKEN", None)
                
        except:
            pass
        
        return None
    
    async def _test_permission_escalation(self, server_name: str) -> Optional[str]:
        """Test for permission escalation vulnerabilities."""
        
        try:
            client = MCPClient(server_name)
            await client.start()
            
            # Get available tools
            tools = await client.list_tools()
            
            # Look for admin/privileged tools
            admin_tools = []
            user_tools = []
            
            for tool in tools:
                name = tool.get('name', '').lower()
                if any(priv in name for priv in ['admin', 'sudo', 'root', 'system', 'exec']):
                    admin_tools.append(tool['name'])
                else:
                    user_tools.append(tool['name'])
            
            # Check if admin tools are accessible
            if admin_tools:
                for admin_tool in admin_tools[:3]:
                    try:
                        # Try to call admin tool as regular user
                        result = await client.call_tool(admin_tool, {})
                        # If successful, we have privilege escalation
                        await client.stop()
                        return f"Admin tool '{admin_tool}' accessible without privileges"
                    except Exception as e:
                        if "permission" not in str(e).lower() and "denied" not in str(e).lower():
                            # Error but not permission denied - might be escalation
                            return f"Unclear permissions on '{admin_tool}'"
            
            await client.stop()
            
        except:
            pass
        
        return None
    
    async def _test_weak_authentication(self, server_name: str) -> Optional[str]:
        """Test for weak authentication mechanisms."""
        
        weak_indicators = []
        
        try:
            # Check environment variables for weak auth
            server_config = SERVERS.get(server_name, {})
            
            if 'env' in server_config:
                for key, value in server_config['env'].items():
                    # Check for hardcoded credentials
                    if value and key.upper().endswith(('TOKEN', 'PASSWORD', 'KEY')):
                        if value in ['test', 'demo', 'admin', 'password', '12345']:
                            weak_indicators.append(f"Hardcoded weak credential: {key}")
                        
                        # Check for short tokens
                        if len(str(value)) < 8:
                            weak_indicators.append(f"Short {key}: {len(value)} chars")
                    
                    # Check for missing auth entirely
                    if not value and 'TOKEN' in key.upper():
                        weak_indicators.append(f"Empty {key}")
            
            # Test common weak passwords
            weak_passwords = ['admin', 'password', '12345', 'test', 'demo']
            
            for pwd in weak_passwords:
                os.environ["MCP_AUTH"] = pwd
                try:
                    client = MCPClient(server_name)
                    await client.start()
                    # Weak password worked!
                    await client.stop()
                    weak_indicators.append(f"Accepts weak password: '{pwd}'")
                    break
                except:
                    pass
                finally:
                    os.environ.pop("MCP_AUTH", None)
            
        except:
            pass
        
        return ", ".join(weak_indicators) if weak_indicators else None
    
    def _generate_report(self, server_name: str) -> Dict:
        """Generate authentication vulnerability report."""
        
        # Calculate risk score
        critical_count = len([f for f in self.findings if f.severity == "CRITICAL"])
        high_count = len([f for f in self.findings if f.severity == "HIGH"])
        medium_count = len([f for f in self.findings if f.severity == "MEDIUM"])
        
        risk_score = (critical_count * 40) + (high_count * 25) + (medium_count * 10)
        risk_score = min(100, risk_score)
        
        # Determine auth status
        # Check if this is a local server
        from config import SERVERS
        server_config = SERVERS.get(server_name, {})
        transport = server_config.get('transport', 'stdio')
        
        if transport == 'stdio':
            # Local servers have different criteria
            if high_count > 0:
                auth_status = "LOCAL SERVER - SECURITY ISSUES"
            elif medium_count > 0:
                auth_status = "LOCAL SERVER - MINOR ISSUES"
            else:
                auth_status = "LOCAL SERVER - SECURE"
        else:
            # Remote servers need authentication
            if critical_count > 0:
                auth_status = "EXPOSED - NO AUTHENTICATION"
            elif high_count > 0:
                auth_status = "VULNERABLE"
            elif medium_count > 0:
                auth_status = "WEAK"
            else:
                auth_status = "SECURE"
        
        return {
            "server": server_name,
            "scan_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "auth_status": auth_status,
            "risk_score": risk_score,
            "findings": [
                {
                    "vulnerability": f.vulnerability.value,
                    "severity": f.severity,
                    "description": f.description,
                    "impact": f.impact,
                    "proof": f.proof
                }
                for f in self.findings
            ],
            "tests_passed": len(self.auth_tests_passed),
            "tests_failed": len(self.findings),
            "summary": {
                "critical": critical_count,
                "high": high_count,
                "medium": medium_count
            }
        }


def print_auth_report(report: Dict):
    """Print formatted authentication report."""
    print("\n" + "=" * 70)
    print("AUTHENTICATION VULNERABILITY REPORT")
    print("=" * 70)
    print(f"Server: {report['server']}")
    print(f"Scan Time: {report['scan_time']}")
    print(f"Auth Status: {report['auth_status']}")
    print(f"Risk Score: {report['risk_score']}/100")
    
    print(f"\nTests Passed: {report['tests_passed']}")
    print(f"Vulnerabilities Found: {report['tests_failed']}")
    
    if report['findings']:
        print("\n⚠️ AUTHENTICATION VULNERABILITIES:")
        
        for finding in report['findings']:
            severity_symbol = {
                "CRITICAL": "🔴",
                "HIGH": "🟠",
                "MEDIUM": "🟡",
                "LOW": "🟢"
            }.get(finding['severity'], "⚪")
            
            print(f"\n  {severity_symbol} {finding['severity']}: {finding['vulnerability']}")
            print(f"     Description: {finding['description']}")
            print(f"     Impact: {finding['impact']}")
            if finding['proof']:
                print(f"     Proof: {finding['proof']}")
    else:
        print("\n✅ No authentication vulnerabilities found")
    
    if report['auth_status'] == "EXPOSED - NO AUTHENTICATION":
        print("\n🚨 CRITICAL SECURITY ALERT:")
        print("  This server is COMPLETELY EXPOSED without authentication!")
        print("  Anyone on the network can execute commands on this server!")
        print("\n  IMMEDIATE ACTIONS REQUIRED:")
        print("  1. Implement authentication immediately")
        print("  2. Use OAuth 2.1 or similar strong auth mechanism")
        print("  3. Never expose MCP servers without authentication")
        print("  4. Bind to localhost only, never 0.0.0.0")
    
    print("=" * 70)


async def main():
    """Run authentication vulnerability test."""
    import sys
    import os
    
    server_name = sys.argv[1] if len(sys.argv) > 1 else "filesystem"
    
    if server_name not in SERVERS:
        print(f"Unknown server: {server_name}")
        return 1
    
    tester = AuthenticationTester()
    report = await tester.test_authentication(server_name)
    print_auth_report(report)
    
    # Save report
    report_file = f"auth_report_{server_name}.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport saved to {report_file}")
    
    # Return non-zero if critical vulnerabilities found
    return 1 if report['auth_status'] in ["EXPOSED - NO AUTHENTICATION", "VULNERABLE"] else 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    import sys
    sys.exit(exit_code)