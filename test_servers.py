#!/usr/bin/env python3
"""
Test script to verify multiple MCP server support.
Tests each configured server and reports compatibility.
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, List

from mcp_client import MCPClient
from config import SERVERS, TEST_DIR


class ServerTester:
    """Test MCP servers for compatibility and functionality."""
    
    def __init__(self):
        self.results = {}
    
    async def test_server(self, server_name: str) -> Dict:
        """Test a single MCP server."""
        result = {
            'name': server_name,
            'status': 'unknown',
            'tools_count': 0,
            'error': None,
            'description': SERVERS.get(server_name, {}).get('description', 'No description')
        }
        
        # Check for required environment variables
        server_config = SERVERS.get(server_name, {})
        missing_env = []
        if 'env' in server_config:
            for key, value in server_config['env'].items():
                if not value and 'TOKEN' in key:
                    missing_env.append(key)
        
        if missing_env:
            result['status'] = 'skipped'
            result['error'] = f"Missing required env vars: {', '.join(missing_env)}"
            return result
        
        # Try to start and test the server
        try:
            print(f"Testing {server_name}...")
            client = MCPClient(server_name)
            
            # Start server with timeout
            await asyncio.wait_for(client.start(), timeout=10)
            
            # List tools
            tools = await asyncio.wait_for(client.list_tools(), timeout=5)
            result['tools_count'] = len(tools)
            result['status'] = 'working'
            
            # Stop server
            await client.stop()
            
        except asyncio.TimeoutError:
            result['status'] = 'timeout'
            result['error'] = 'Server startup or tool listing timed out'
        except Exception as e:
            result['status'] = 'failed'
            result['error'] = str(e)[:100]
        
        return result
    
    async def test_all_servers(self) -> Dict:
        """Test all configured servers."""
        print("=" * 60)
        print("MCP SERVER COMPATIBILITY TEST")
        print("=" * 60)
        
        for server_name in SERVERS.keys():
            result = await self.test_server(server_name)
            self.results[server_name] = result
            
            # Print result
            status_symbol = {
                'working': '✓',
                'failed': '✗',
                'timeout': '⏱',
                'skipped': '○'
            }.get(result['status'], '?')
            
            print(f"{status_symbol} {server_name:15} - {result['description']}")
            if result['status'] == 'working':
                print(f"  └─ {result['tools_count']} tools available")
            elif result['error']:
                print(f"  └─ {result['error']}")
        
        return self.results
    
    def generate_report(self) -> str:
        """Generate a compatibility report."""
        report = []
        report.append("\n" + "=" * 60)
        report.append("SERVER COMPATIBILITY MATRIX")
        report.append("=" * 60)
        
        working = []
        failed = []
        skipped = []
        
        for name, result in self.results.items():
            if result['status'] == 'working':
                working.append((name, result['tools_count']))
            elif result['status'] == 'skipped':
                skipped.append((name, result['error']))
            else:
                failed.append((name, result['error']))
        
        if working:
            report.append("\n✓ WORKING SERVERS:")
            for name, tools in working:
                report.append(f"  - {name}: {tools} tools")
        
        if failed:
            report.append("\n✗ FAILED SERVERS:")
            for name, error in failed:
                report.append(f"  - {name}: {error}")
        
        if skipped:
            report.append("\n○ SKIPPED (MISSING CONFIG):")
            for name, error in skipped:
                report.append(f"  - {name}: {error}")
        
        # Summary
        total = len(self.results)
        working_count = len(working)
        report.append(f"\nSUMMARY: {working_count}/{total} servers working")
        
        # Recommendations
        if skipped:
            report.append("\nTo test more servers, set environment variables:")
            seen = set()
            for name, error in skipped:
                if 'GITHUB_TOKEN' in error and 'GITHUB_TOKEN' not in seen:
                    report.append("  export GITHUB_TOKEN='your-github-token'")
                    seen.add('GITHUB_TOKEN')
                if 'SLACK_TOKEN' in error and 'SLACK_TOKEN' not in seen:
                    report.append("  export SLACK_TOKEN='your-slack-token'")
                    seen.add('SLACK_TOKEN')
                if 'POSTGRES' in error and 'POSTGRES' not in seen:
                    report.append("  # Set up PostgreSQL connection:")
                    report.append("  export POSTGRES_HOST='localhost'")
                    report.append("  export POSTGRES_USER='postgres'")
                    report.append("  export POSTGRES_PASSWORD='your-password'")
                    seen.add('POSTGRES')
        
        return '\n'.join(report)


async def main():
    """Run server compatibility tests."""
    tester = ServerTester()
    
    # Test all servers
    await tester.test_all_servers()
    
    # Generate and print report
    report = tester.generate_report()
    print(report)
    
    # Save report to file
    with open('server_compatibility.txt', 'w') as f:
        f.write(report)
    print(f"\nReport saved to server_compatibility.txt")
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)