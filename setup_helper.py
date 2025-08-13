#!/usr/bin/env python3
"""
MCP Setup Helper
Helps developers quickly set up MCP servers and verify installations.
Automates common setup tasks and checks for common problems.
"""

import asyncio
import json
import os
import subprocess
import sys
import platform
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class SetupStatus(Enum):
    """Setup status types."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class SetupStep:
    """A setup step."""
    name: str
    description: str
    command: Optional[str] = None
    check_command: Optional[str] = None
    status: SetupStatus = SetupStatus.NOT_STARTED
    error: Optional[str] = None


class SetupHelper:
    """Help users set up MCP servers."""
    
    # Common MCP servers and their installation commands
    MCP_SERVERS = {
        "filesystem": {
            "name": "@modelcontextprotocol/server-filesystem",
            "install": "npm install -g @modelcontextprotocol/server-filesystem",
            "check": "npm list -g @modelcontextprotocol/server-filesystem",
            "description": "File system access server"
        },
        "github": {
            "name": "@modelcontextprotocol/server-github",
            "install": "npm install -g @modelcontextprotocol/server-github",
            "check": "npm list -g @modelcontextprotocol/server-github",
            "description": "GitHub repository access"
        },
        "postgres": {
            "name": "@henkey/postgres-mcp-server",
            "install": "npm install -g @henkey/postgres-mcp-server",
            "check": "npm list -g @henkey/postgres-mcp-server",
            "description": "PostgreSQL database access"
        },
        "slack": {
            "name": "@modelcontextprotocol/server-slack",
            "install": "npm install -g @modelcontextprotocol/server-slack",
            "check": "npm list -g @modelcontextprotocol/server-slack",
            "description": "Slack workspace access"
        },
        "git": {
            "name": "@modelcontextprotocol/server-git",
            "install": "npm install -g @modelcontextprotocol/server-git",
            "check": "npm list -g @modelcontextprotocol/server-git",
            "description": "Git repository operations"
        },
        "google-drive": {
            "name": "@modelcontextprotocol/server-google-drive",
            "install": "npm install -g @modelcontextprotocol/server-google-drive",
            "check": "npm list -g @modelcontextprotocol/server-google-drive",
            "description": "Google Drive access"
        },
        "sqlite": {
            "name": "@modelcontextprotocol/server-sqlite",
            "install": "npm install -g @modelcontextprotocol/server-sqlite",
            "check": "npm list -g @modelcontextprotocol/server-sqlite",
            "description": "SQLite database access"
        }
    }
    
    def __init__(self):
        self.setup_steps = []
        self.system_info = self._get_system_info()
    
    def _get_system_info(self) -> Dict:
        """Get system information."""
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "python_version": sys.version.split()[0],
            "node_version": self._get_node_version(),
            "npm_version": self._get_npm_version(),
            "home_dir": str(Path.home())
        }
    
    def _get_node_version(self) -> Optional[str]:
        """Get Node.js version."""
        try:
            result = subprocess.run(["node", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except FileNotFoundError:
            pass
        return None
    
    def _get_npm_version(self) -> Optional[str]:
        """Get npm version."""
        try:
            result = subprocess.run(["npm", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except FileNotFoundError:
            pass
        return None
    
    async def check_prerequisites(self) -> Dict:
        """Check if prerequisites are installed."""
        
        print(f"\n{'=' * 70}")
        print("CHECKING PREREQUISITES")
        print(f"{'=' * 70}")
        
        prereqs = {
            "node": False,
            "npm": False,
            "python": True,  # We're running Python
            "git": False
        }
        
        # Check Node.js
        if self.system_info["node_version"]:
            prereqs["node"] = True
            print(f"✅ Node.js: {self.system_info['node_version']}")
        else:
            print("❌ Node.js: Not installed")
            print("   Install from: https://nodejs.org/")
        
        # Check npm
        if self.system_info["npm_version"]:
            prereqs["npm"] = True
            print(f"✅ npm: {self.system_info['npm_version']}")
        else:
            print("❌ npm: Not installed")
            print("   Usually comes with Node.js")
        
        # Check Python
        print(f"✅ Python: {self.system_info['python_version']}")
        
        # Check git
        try:
            result = subprocess.run(["git", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                prereqs["git"] = True
                print(f"✅ git: {result.stdout.strip()}")
            else:
                print("❌ git: Not installed")
        except FileNotFoundError:
            print("❌ git: Not installed")
            print("   Install from: https://git-scm.com/")
        
        return prereqs
    
    async def install_server(self, server_name: str) -> bool:
        """Install a specific MCP server."""
        
        if server_name not in self.MCP_SERVERS:
            print(f"❌ Unknown server: {server_name}")
            print(f"   Available: {', '.join(self.MCP_SERVERS.keys())}")
            return False
        
        server_info = self.MCP_SERVERS[server_name]
        
        print(f"\n📦 Installing {server_name}...")
        print(f"   Package: {server_info['name']}")
        print(f"   Description: {server_info['description']}")
        
        # Check if already installed
        try:
            result = subprocess.run(
                server_info["check"].split(),
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print(f"   ✅ Already installed")
                return True
        except:
            pass
        
        # Install
        print(f"   Running: {server_info['install']}")
        try:
            result = subprocess.run(
                server_info["install"].split(),
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print(f"   ✅ Successfully installed")
                return True
            else:
                print(f"   ❌ Installation failed")
                if result.stderr:
                    print(f"   Error: {result.stderr[:200]}")
                return False
        except Exception as e:
            print(f"   ❌ Installation error: {e}")
            return False
    
    async def setup_claude_desktop(self) -> Dict:
        """Set up Claude Desktop configuration."""
        
        print(f"\n{'=' * 70}")
        print("SETTING UP CLAUDE DESKTOP")
        print(f"{'=' * 70}")
        
        # Determine config path based on OS
        if self.system_info["os"] == "Darwin":  # macOS
            config_dir = Path.home() / "Library" / "Application Support" / "Claude"
        elif self.system_info["os"] == "Windows":
            config_dir = Path.home() / "AppData" / "Roaming" / "Claude"
        else:  # Linux
            config_dir = Path.home() / ".config" / "claude"
        
        config_file = config_dir / "claude_desktop_config.json"
        
        print(f"\n📁 Config location: {config_file}")
        
        # Create directory if needed
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if config exists
        if config_file.exists():
            print("   Config file exists")
            
            # Load and validate
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                print("   ✅ Config is valid JSON")
                
                # Check for mcpServers
                if "mcpServers" in config:
                    servers = config["mcpServers"]
                    print(f"   Found {len(servers)} configured servers:")
                    for name in servers:
                        print(f"     • {name}")
                else:
                    print("   ⚠️ No MCP servers configured")
                    
            except json.JSONDecodeError as e:
                print(f"   ❌ Invalid JSON: {e}")
        else:
            print("   Config file doesn't exist")
            
            # Create sample config
            print("\n   Creating sample configuration...")
            
            sample_config = {
                "mcpServers": {
                    "filesystem": {
                        "command": "npx",
                        "args": [
                            "-y",
                            "@modelcontextprotocol/server-filesystem",
                            str(Path.home())
                        ]
                    }
                }
            }
            
            with open(config_file, 'w') as f:
                json.dump(sample_config, f, indent=2)
            
            print(f"   ✅ Created sample config with filesystem server")
            print(f"   Edit {config_file} to add more servers")
        
        return {
            "config_path": str(config_file),
            "exists": config_file.exists(),
            "valid": True
        }
    
    async def test_server_connection(self, server_name: str) -> bool:
        """Test if a server can be connected to."""
        
        print(f"\n🧪 Testing {server_name} server...")
        
        # Import our MCP client
        try:
            from mcp_client import MCPClient
            from config import SERVERS
            
            if server_name not in SERVERS:
                print(f"   ❌ Server not configured in config.py")
                return False
            
            client = MCPClient(server_name)
            
            # Try to connect
            await client.start()
            print(f"   ✅ Connected successfully")
            
            # Try to list tools
            tools = await client.list_tools()
            print(f"   Found {len(tools)} tools")
            
            await client.stop()
            return True
            
        except Exception as e:
            print(f"   ❌ Connection failed: {e}")
            return False
    
    async def quick_setup(self) -> Dict:
        """Run quick setup for common servers."""
        
        print(f"\n{'=' * 70}")
        print("MCP QUICK SETUP")
        print(f"{'=' * 70}")
        
        results = {
            "prerequisites": {},
            "servers_installed": [],
            "claude_desktop": {},
            "tests_passed": []
        }
        
        # Check prerequisites
        print("\n1️⃣ Checking prerequisites...")
        results["prerequisites"] = await self.check_prerequisites()
        
        if not results["prerequisites"]["node"] or not results["prerequisites"]["npm"]:
            print("\n⚠️ Node.js and npm are required for MCP servers")
            print("Install from: https://nodejs.org/")
            return results
        
        # Install common servers
        print("\n2️⃣ Installing common MCP servers...")
        
        common_servers = ["filesystem", "github", "sqlite"]
        
        for server in common_servers:
            if await self.install_server(server):
                results["servers_installed"].append(server)
        
        # Set up Claude Desktop
        print("\n3️⃣ Setting up Claude Desktop...")
        results["claude_desktop"] = await self.setup_claude_desktop()
        
        # Test connections
        print("\n4️⃣ Testing server connections...")
        
        for server in results["servers_installed"]:
            if await self.test_server_connection(server):
                results["tests_passed"].append(server)
        
        # Print summary
        self._print_setup_summary(results)
        
        return results
    
    def _print_setup_summary(self, results: Dict):
        """Print setup summary."""
        
        print(f"\n{'=' * 70}")
        print("SETUP COMPLETE")
        print(f"{'=' * 70}")
        
        # Prerequisites
        prereq_ok = all(results["prerequisites"].values())
        symbol = "✅" if prereq_ok else "⚠️"
        print(f"\n{symbol} Prerequisites:")
        for name, installed in results["prerequisites"].items():
            symbol = "✅" if installed else "❌"
            print(f"   {symbol} {name}")
        
        # Servers
        if results["servers_installed"]:
            print(f"\n✅ Servers Installed ({len(results['servers_installed'])}):")
            for server in results["servers_installed"]:
                print(f"   • {server}")
        else:
            print("\n❌ No servers installed")
        
        # Claude Desktop
        if results["claude_desktop"].get("valid"):
            print(f"\n✅ Claude Desktop configured")
            print(f"   Config: {results['claude_desktop']['config_path']}")
        else:
            print("\n❌ Claude Desktop configuration failed")
        
        # Tests
        if results["tests_passed"]:
            print(f"\n✅ Connection Tests Passed ({len(results['tests_passed'])}):")
            for server in results["tests_passed"]:
                print(f"   • {server}")
        
        # Next steps
        print(f"\n📝 Next Steps:")
        
        if not prereq_ok:
            print("   1. Install missing prerequisites")
        
        if not results["servers_installed"]:
            print("   2. Install MCP servers with npm")
        
        if results["claude_desktop"].get("valid"):
            print("   3. Restart Claude Desktop to load configuration")
        else:
            print("   3. Configure Claude Desktop")
        
        print("   4. Test with: python connection_debugger.py [server_name]")
        print("   5. Validate config: python config_validator.py [config_file]")
    
    def generate_config_for_client(self, client: str, servers: List[str]) -> Dict:
        """Generate configuration for a specific client."""
        
        configs = {}
        
        for server in servers:
            if server in self.MCP_SERVERS:
                server_info = self.MCP_SERVERS[server]
                
                if client == "claude_desktop":
                    if "mcpServers" not in configs:
                        configs["mcpServers"] = {}
                    
                    configs["mcpServers"][server] = {
                        "command": "npx",
                        "args": ["-y", server_info["name"]]
                    }
                    
                    # Add specific args for certain servers
                    if server == "filesystem":
                        configs["mcpServers"][server]["args"].append(str(Path.home()))
                
                elif client == "cursor":
                    if "mcp" not in configs:
                        configs["mcp"] = {"servers": {}}
                    
                    configs["mcp"]["servers"][server] = {
                        "command": "npx",
                        "args": ["-y", server_info["name"]]
                    }
                
                elif client == "cline":
                    if "servers" not in configs:
                        configs["servers"] = []
                    
                    configs["servers"].append({
                        "name": server,
                        "command": "npx",
                        "args": ["-y", server_info["name"]]
                    })
        
        return configs


async def main():
    """Run setup helper."""
    
    helper = SetupHelper()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "check":
            # Check prerequisites only
            await helper.check_prerequisites()
        
        elif command == "install":
            # Install specific server
            if len(sys.argv) > 2:
                server = sys.argv[2]
                await helper.install_server(server)
            else:
                print("Usage: python setup_helper.py install <server_name>")
                print(f"Available servers: {', '.join(helper.MCP_SERVERS.keys())}")
        
        elif command == "claude":
            # Set up Claude Desktop
            await helper.setup_claude_desktop()
        
        elif command == "test":
            # Test server connection
            if len(sys.argv) > 2:
                server = sys.argv[2]
                await helper.test_server_connection(server)
            else:
                print("Usage: python setup_helper.py test <server_name>")
        
        elif command == "config":
            # Generate config for client
            if len(sys.argv) > 2:
                client = sys.argv[2]
                servers = ["filesystem", "github", "sqlite"]
                config = helper.generate_config_for_client(client, servers)
                print(json.dumps(config, indent=2))
            else:
                print("Usage: python setup_helper.py config <client>")
                print("Clients: claude_desktop, cursor, cline")
        
        else:
            print(f"Unknown command: {command}")
            print("Commands: check, install, claude, test, config")
    
    else:
        # Run quick setup
        await helper.quick_setup()
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)