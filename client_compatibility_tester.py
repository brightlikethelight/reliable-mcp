#!/usr/bin/env python3
"""
MCP Client Compatibility Tester
Tests which MCP servers work with which clients (Claude Desktop, Cursor, Cline, etc).
Helps developers understand compatibility issues between different MCP implementations.
"""

import asyncio
import json
import os
import subprocess
import sys
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from mcp_client import MCPClient
from config import SERVERS


class ClientType(Enum):
    """Known MCP client types."""
    CLAUDE_DESKTOP = "claude_desktop"
    CURSOR = "cursor"
    CLINE = "cline"
    CONTINUE = "continue"
    AIDER = "aider"
    CUSTOM = "custom"


@dataclass
class CompatibilityTest:
    """Result of a compatibility test."""
    client: ClientType
    server: str
    compatible: bool
    issues: List[str]
    notes: List[str]
    config_format: Optional[str] = None


class ClientCompatibilityTester:
    """Test MCP server compatibility with different clients."""
    
    # Known client requirements and quirks
    CLIENT_REQUIREMENTS = {
        ClientType.CLAUDE_DESKTOP: {
            "config_format": "mcpServers",
            "transport": ["stdio"],
            "auth": False,
            "notes": [
                "Only supports stdio transport",
                "No network server support",
                "Requires 'command' and optional 'args' fields"
            ]
        },
        ClientType.CURSOR: {
            "config_format": "mcp.servers",
            "transport": ["stdio", "http"],
            "auth": True,
            "notes": [
                "Supports both stdio and HTTP transports",
                "Can handle OAuth for remote servers",
                "Config nested under 'mcp.servers'"
            ]
        },
        ClientType.CLINE: {
            "config_format": "servers[]",
            "transport": ["stdio"],
            "auth": False,
            "notes": [
                "Uses array format for servers",
                "Each server needs 'name' field",
                "Limited to stdio transport"
            ]
        },
        ClientType.CONTINUE: {
            "config_format": "providers",
            "transport": ["stdio", "http"],
            "auth": True,
            "notes": [
                "Uses 'providers' instead of 'servers'",
                "Supports multiple transports",
                "Can integrate with IDE authentication"
            ]
        },
        ClientType.AIDER: {
            "config_format": "tools",
            "transport": ["stdio"],
            "auth": False,
            "notes": [
                "Uses 'tools' configuration",
                "Command-line focused",
                "No GUI configuration"
            ]
        }
    }
    
    def __init__(self):
        self.test_results = []
        self.compatibility_matrix = {}
    
    async def test_all_compatibility(self) -> Dict:
        """Test all servers against all known clients."""
        
        print(f"\n{'=' * 70}")
        print("MCP CLIENT COMPATIBILITY TESTING")
        print(f"{'=' * 70}")
        
        # Test each server against each client
        for server_name in SERVERS.keys():
            print(f"\n📦 Testing server: {server_name}")
            
            for client_type in ClientType:
                if client_type == ClientType.CUSTOM:
                    continue
                    
                result = await self.test_compatibility(server_name, client_type)
                self.test_results.append(result)
                
                # Update matrix
                if server_name not in self.compatibility_matrix:
                    self.compatibility_matrix[server_name] = {}
                self.compatibility_matrix[server_name][client_type.value] = result.compatible
                
                # Print result
                symbol = "✅" if result.compatible else "❌"
                print(f"  {symbol} {client_type.value}: {'Compatible' if result.compatible else 'Incompatible'}")
                
                if result.issues:
                    for issue in result.issues[:2]:  # Show first 2 issues
                        print(f"     • {issue}")
        
        return self._generate_report()
    
    async def test_compatibility(self, server_name: str, client_type: ClientType) -> CompatibilityTest:
        """Test if a server is compatible with a specific client."""
        
        server_config = SERVERS.get(server_name, {})
        client_reqs = self.CLIENT_REQUIREMENTS.get(client_type, {})
        
        issues = []
        notes = []
        compatible = True
        
        # Check transport compatibility
        server_transport = server_config.get('transport', 'stdio')
        supported_transports = client_reqs.get('transport', [])
        
        if server_transport not in supported_transports:
            issues.append(f"Transport '{server_transport}' not supported (requires: {', '.join(supported_transports)})")
            compatible = False
        
        # Check authentication requirements
        requires_auth = client_reqs.get('auth', False)
        server_has_auth = bool(server_config.get('env', {}).get('API_KEY') or 
                              server_config.get('env', {}).get('TOKEN'))
        
        if requires_auth and not server_has_auth and server_transport == 'http':
            issues.append("Client requires authentication for HTTP servers")
            notes.append("Add API_KEY or TOKEN to server configuration")
        
        # Check configuration format
        config_format = client_reqs.get('config_format')
        notes.append(f"Config format: {config_format}")
        
        # Test actual connection if possible
        if compatible:
            connection_test = await self._test_actual_connection(server_name, client_type)
            if not connection_test['success']:
                issues.append(f"Connection test failed: {connection_test.get('error', 'Unknown error')}")
                compatible = False
        
        # Add client-specific notes
        notes.extend(client_reqs.get('notes', []))
        
        return CompatibilityTest(
            client=client_type,
            server=server_name,
            compatible=compatible,
            issues=issues,
            notes=notes,
            config_format=config_format
        )
    
    async def _test_actual_connection(self, server_name: str, client_type: ClientType) -> Dict:
        """Test actual connection with server."""
        
        try:
            client = MCPClient(server_name)
            await client.start()
            
            # Basic connectivity test
            tools = await client.list_tools()
            
            # Client-specific tests
            if client_type == ClientType.CLAUDE_DESKTOP:
                # Claude Desktop specific requirements
                if not isinstance(tools, list):
                    return {"success": False, "error": "Tools must be a list"}
            
            elif client_type == ClientType.CURSOR:
                # Cursor specific requirements
                pass  # Cursor is generally compatible
            
            elif client_type == ClientType.CLINE:
                # Cline specific requirements
                if len(tools) > 100:
                    return {"success": False, "error": "Cline may struggle with >100 tools"}
            
            await client.stop()
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def generate_config_for_client(self, server_name: str, client_type: ClientType) -> Dict:
        """Generate a valid configuration for a specific client."""
        
        server_config = SERVERS.get(server_name, {})
        client_reqs = self.CLIENT_REQUIREMENTS.get(client_type, {})
        
        # Build configuration based on client format
        if client_type == ClientType.CLAUDE_DESKTOP:
            return {
                "mcpServers": {
                    server_name: {
                        "command": server_config.get('command', ['npx'])[0],
                        "args": server_config.get('command', [])[1:] + server_config.get('args', []),
                        "env": server_config.get('env', {})
                    }
                }
            }
        
        elif client_type == ClientType.CURSOR:
            return {
                "mcp": {
                    "servers": {
                        server_name: {
                            "command": server_config.get('command', ['npx'])[0],
                            "args": server_config.get('command', [])[1:] + server_config.get('args', []),
                            "env": server_config.get('env', {})
                        }
                    }
                }
            }
        
        elif client_type == ClientType.CLINE:
            return {
                "servers": [{
                    "name": server_name,
                    "command": server_config.get('command', ['npx'])[0],
                    "args": server_config.get('command', [])[1:] + server_config.get('args', []),
                    "env": server_config.get('env', {})
                }]
            }
        
        elif client_type == ClientType.CONTINUE:
            return {
                "providers": {
                    server_name: {
                        "type": "mcp",
                        "command": server_config.get('command', ['npx'])[0],
                        "args": server_config.get('command', [])[1:] + server_config.get('args', []),
                        "env": server_config.get('env', {})
                    }
                }
            }
        
        elif client_type == ClientType.AIDER:
            return {
                "tools": {
                    server_name: {
                        "command": " ".join(server_config.get('command', []) + server_config.get('args', [])),
                        "env": server_config.get('env', {})
                    }
                }
            }
        
        return {}
    
    def _generate_report(self) -> Dict:
        """Generate compatibility report."""
        
        # Calculate statistics
        total_tests = len(self.test_results)
        compatible_count = sum(1 for r in self.test_results if r.compatible)
        
        # Find best client for each server
        best_clients = {}
        for server in self.compatibility_matrix:
            compatible_clients = [
                client for client, compat in self.compatibility_matrix[server].items()
                if compat
            ]
            best_clients[server] = compatible_clients
        
        # Find best servers for each client
        best_servers = {}
        for client_type in ClientType:
            if client_type == ClientType.CUSTOM:
                continue
            compatible_servers = [
                server for server in self.compatibility_matrix
                if self.compatibility_matrix[server].get(client_type.value, False)
            ]
            best_servers[client_type.value] = compatible_servers
        
        print(f"\n{'=' * 70}")
        print("COMPATIBILITY MATRIX")
        print(f"{'=' * 70}")
        
        # Print matrix
        print(f"\n{'Server':<20}", end="")
        for client_type in ClientType:
            if client_type != ClientType.CUSTOM:
                print(f"{client_type.value:<15}", end="")
        print()
        
        print("-" * 95)
        
        for server in self.compatibility_matrix:
            print(f"{server:<20}", end="")
            for client_type in ClientType:
                if client_type != ClientType.CUSTOM:
                    compat = self.compatibility_matrix[server].get(client_type.value, False)
                    symbol = "✅" if compat else "❌"
                    print(f"{symbol:<15}", end="")
            print()
        
        print(f"\n{'=' * 70}")
        print("RECOMMENDATIONS")
        print(f"{'=' * 70}")
        
        # Best client for each server
        print("\n🎯 Best Clients for Each Server:")
        for server, clients in best_clients.items():
            if clients:
                print(f"  {server}: {', '.join(clients)}")
            else:
                print(f"  {server}: ⚠️ No compatible clients found")
        
        # Best servers for each client
        print("\n🎯 Best Servers for Each Client:")
        for client, servers in best_servers.items():
            if servers:
                print(f"  {client}: {', '.join(servers[:3])}")  # Show top 3
            else:
                print(f"  {client}: ⚠️ No compatible servers found")
        
        # Common issues
        all_issues = []
        for result in self.test_results:
            all_issues.extend(result.issues)
        
        if all_issues:
            print("\n⚠️ Common Issues Found:")
            issue_counts = {}
            for issue in all_issues:
                # Simplify issue for grouping
                key = issue.split(':')[0] if ':' in issue else issue
                issue_counts[key] = issue_counts.get(key, 0) + 1
            
            for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"  • {issue} ({count} occurrences)")
        
        print(f"\n📊 Summary:")
        print(f"  Total Tests: {total_tests}")
        print(f"  Compatible: {compatible_count} ({compatible_count/total_tests*100:.1f}%)")
        print(f"  Incompatible: {total_tests - compatible_count} ({(total_tests - compatible_count)/total_tests*100:.1f}%)")
        
        return {
            "total_tests": total_tests,
            "compatible_count": compatible_count,
            "compatibility_matrix": self.compatibility_matrix,
            "best_clients": best_clients,
            "best_servers": best_servers,
            "test_results": [
                {
                    "client": r.client.value,
                    "server": r.server,
                    "compatible": r.compatible,
                    "issues": r.issues,
                    "notes": r.notes
                }
                for r in self.test_results
            ]
        }


async def main():
    """Run client compatibility tests."""
    
    if len(sys.argv) > 1:
        # Test specific server
        server_name = sys.argv[1]
        
        if server_name not in SERVERS:
            print(f"Unknown server: {server_name}")
            print(f"Available servers: {', '.join(SERVERS.keys())}")
            return 1
        
        tester = ClientCompatibilityTester()
        
        print(f"\n{'=' * 70}")
        print(f"Testing {server_name} with all clients")
        print(f"{'=' * 70}")
        
        for client_type in ClientType:
            if client_type == ClientType.CUSTOM:
                continue
            
            result = await tester.test_compatibility(server_name, client_type)
            
            symbol = "✅" if result.compatible else "❌"
            print(f"\n{symbol} {client_type.value}: {'Compatible' if result.compatible else 'Incompatible'}")
            
            if result.issues:
                print("  Issues:")
                for issue in result.issues:
                    print(f"    • {issue}")
            
            if result.notes:
                print("  Notes:")
                for note in result.notes[:2]:  # Show first 2 notes
                    print(f"    • {note}")
            
            # Generate sample config
            if result.compatible:
                config = tester.generate_config_for_client(server_name, client_type)
                print(f"  Sample config:")
                print(f"    {json.dumps(config, indent=2)[:200]}...")
        
        return 0
    
    else:
        # Test all combinations
        tester = ClientCompatibilityTester()
        report = await tester.test_all_compatibility()
        
        # Save report
        report_file = "client_compatibility_report.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\n✅ Report saved to {report_file}")
        
        return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)