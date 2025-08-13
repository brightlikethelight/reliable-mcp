#!/usr/bin/env python3
"""
MCP Configuration Validator
Validates MCP server configurations for Claude Desktop, Cursor, Cline, etc.
Helps developers fix the #2 most common problem: configuration issues.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ConfigFormat(Enum):
    """Configuration format types."""
    CLAUDE_DESKTOP = "claude_desktop"
    CURSOR = "cursor"
    CLINE = "cline"
    GENERIC = "generic"


@dataclass
class ConfigIssue:
    """A configuration issue found."""
    severity: str  # error, warning, info
    field: str
    message: str
    suggestion: str


class ConfigurationValidator:
    """Validate MCP server configurations."""
    
    # Claude Desktop config schema
    CLAUDE_DESKTOP_SCHEMA = {
        "mcpServers": {
            "type": "object",
            "properties": {
                "*": {  # Each server
                    "type": "object",
                    "required": ["command"],
                    "properties": {
                        "command": {"type": "string"},
                        "args": {"type": "array"},
                        "env": {"type": "object"}
                    }
                }
            }
        }
    }
    
    def __init__(self):
        self.issues = []
        self.valid_servers = []
        self.invalid_servers = []
    
    def validate_config_file(self, config_path: str) -> Dict:
        """Validate a configuration file."""
        
        print(f"\n{'=' * 70}")
        print(f"MCP CONFIGURATION VALIDATOR")
        print(f"Validating: {config_path}")
        print(f"{'=' * 70}")
        
        # Check if file exists
        if not os.path.exists(config_path):
            print(f"\n❌ Configuration file not found: {config_path}")
            return {
                "valid": False,
                "error": "File not found",
                "suggestion": f"Create config file at {config_path}"
            }
        
        # Load configuration
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            print(f"\n❌ Invalid JSON: {e}")
            return {
                "valid": False,
                "error": f"JSON parse error: {e}",
                "suggestion": "Fix JSON syntax errors"
            }
        
        # Detect format
        config_format = self._detect_format(config)
        print(f"\nDetected format: {config_format.value}")
        
        # Validate based on format
        if config_format == ConfigFormat.CLAUDE_DESKTOP:
            self._validate_claude_desktop(config)
        elif config_format == ConfigFormat.CURSOR:
            self._validate_cursor(config)
        elif config_format == ConfigFormat.CLINE:
            self._validate_cline(config)
        else:
            self._validate_generic(config)
        
        # Print results
        self._print_validation_results()
        
        return self._generate_report(config_path)
    
    def validate_server_config(self, server_name: str, server_config: Dict) -> List[ConfigIssue]:
        """Validate a single server configuration."""
        
        issues = []
        
        print(f"\n📋 Validating server: {server_name}")
        
        # Check command
        if 'command' not in server_config:
            issues.append(ConfigIssue(
                severity="error",
                field="command",
                message="Missing 'command' field",
                suggestion="Add command field with server executable"
            ))
        else:
            command = server_config['command']
            if not self._validate_command(command):
                issues.append(ConfigIssue(
                    severity="error",
                    field="command",
                    message=f"Command not found: {command}",
                    suggestion=f"Install server or check PATH"
                ))
        
        # Check args
        if 'args' in server_config:
            args = server_config['args']
            if not isinstance(args, list):
                issues.append(ConfigIssue(
                    severity="error",
                    field="args",
                    message="Args must be an array",
                    suggestion="Change args to array format: []"
                ))
            else:
                # Validate each arg
                for arg in args:
                    if not isinstance(arg, str):
                        issues.append(ConfigIssue(
                            severity="warning",
                            field="args",
                            message=f"Arg should be string: {arg}",
                            suggestion="Convert all args to strings"
                        ))
        
        # Check environment variables
        if 'env' in server_config:
            env = server_config['env']
            if not isinstance(env, dict):
                issues.append(ConfigIssue(
                    severity="error",
                    field="env",
                    message="Env must be an object",
                    suggestion="Change env to object format: {}"
                ))
            else:
                # Check for common missing vars
                for key, value in env.items():
                    if not value and ('TOKEN' in key or 'KEY' in key):
                        issues.append(ConfigIssue(
                            severity="warning",
                            field=f"env.{key}",
                            message=f"Empty credential: {key}",
                            suggestion=f"Set {key} to your credential value"
                        ))
        
        # Check for deprecated fields
        if 'stdio' in server_config:
            issues.append(ConfigIssue(
                severity="warning",
                field="stdio",
                message="'stdio' field is deprecated",
                suggestion="Remove 'stdio' field (stdio is default)"
            ))
        
        if 'transport' in server_config:
            transport = server_config['transport']
            if transport == 'sse':
                issues.append(ConfigIssue(
                    severity="error",
                    field="transport",
                    message="SSE transport is deprecated",
                    suggestion="Use 'stdio' or 'http' transport"
                ))
        
        return issues
    
    def _detect_format(self, config: Dict) -> ConfigFormat:
        """Detect configuration format."""
        
        if 'mcpServers' in config:
            return ConfigFormat.CLAUDE_DESKTOP
        elif 'mcp' in config and 'servers' in config.get('mcp', {}):
            return ConfigFormat.CURSOR
        elif 'servers' in config and isinstance(config.get('servers'), list):
            return ConfigFormat.CLINE
        else:
            return ConfigFormat.GENERIC
    
    def _validate_claude_desktop(self, config: Dict):
        """Validate Claude Desktop configuration."""
        
        if 'mcpServers' not in config:
            self.issues.append(ConfigIssue(
                severity="error",
                field="mcpServers",
                message="Missing 'mcpServers' field",
                suggestion="Add mcpServers object to config"
            ))
            return
        
        servers = config['mcpServers']
        
        for server_name, server_config in servers.items():
            issues = self.validate_server_config(server_name, server_config)
            self.issues.extend(issues)
            
            if not any(i.severity == "error" for i in issues):
                self.valid_servers.append(server_name)
                print(f"  ✅ {server_name}: Valid")
            else:
                self.invalid_servers.append(server_name)
                print(f"  ❌ {server_name}: Has errors")
    
    def _validate_cursor(self, config: Dict):
        """Validate Cursor configuration."""
        
        if 'mcp' not in config or 'servers' not in config.get('mcp', {}):
            self.issues.append(ConfigIssue(
                severity="error",
                field="mcp.servers",
                message="Missing 'mcp.servers' field",
                suggestion="Add mcp.servers object to config"
            ))
            return
        
        servers = config['mcp']['servers']
        
        for server_name, server_config in servers.items():
            issues = self.validate_server_config(server_name, server_config)
            self.issues.extend(issues)
            
            if not any(i.severity == "error" for i in issues):
                self.valid_servers.append(server_name)
                print(f"  ✅ {server_name}: Valid")
            else:
                self.invalid_servers.append(server_name)
                print(f"  ❌ {server_name}: Has errors")
    
    def _validate_cline(self, config: Dict):
        """Validate Cline configuration."""
        
        if 'servers' not in config:
            self.issues.append(ConfigIssue(
                severity="error",
                field="servers",
                message="Missing 'servers' field",
                suggestion="Add servers array to config"
            ))
            return
        
        servers = config['servers']
        
        if not isinstance(servers, list):
            self.issues.append(ConfigIssue(
                severity="error",
                field="servers",
                message="Servers must be an array",
                suggestion="Change servers to array format"
            ))
            return
        
        for i, server_config in enumerate(servers):
            server_name = server_config.get('name', f'server_{i}')
            issues = self.validate_server_config(server_name, server_config)
            self.issues.extend(issues)
            
            if not any(i.severity == "error" for i in issues):
                self.valid_servers.append(server_name)
                print(f"  ✅ {server_name}: Valid")
            else:
                self.invalid_servers.append(server_name)
                print(f"  ❌ {server_name}: Has errors")
    
    def _validate_generic(self, config: Dict):
        """Validate generic configuration."""
        
        # Try to find server configurations
        if isinstance(config, dict):
            for key, value in config.items():
                if isinstance(value, dict) and 'command' in value:
                    # Looks like a server config
                    issues = self.validate_server_config(key, value)
                    self.issues.extend(issues)
                    
                    if not any(i.severity == "error" for i in issues):
                        self.valid_servers.append(key)
                    else:
                        self.invalid_servers.append(key)
    
    def _validate_command(self, command: str) -> bool:
        """Check if command exists."""
        
        # Handle npx commands
        if command == 'npx':
            try:
                result = subprocess.run(['which', 'npx'], capture_output=True)
                return result.returncode == 0
            except:
                return False
        
        # Check other commands
        try:
            result = subprocess.run(['which', command], capture_output=True)
            return result.returncode == 0
        except:
            return False
    
    def _print_validation_results(self):
        """Print validation results."""
        
        print(f"\n{'=' * 70}")
        print("VALIDATION RESULTS")
        print(f"{'=' * 70}")
        
        print(f"\nServers found: {len(self.valid_servers) + len(self.invalid_servers)}")
        print(f"  ✅ Valid: {len(self.valid_servers)}")
        print(f"  ❌ Invalid: {len(self.invalid_servers)}")
        
        # Group issues by severity
        errors = [i for i in self.issues if i.severity == "error"]
        warnings = [i for i in self.issues if i.severity == "warning"]
        
        if errors:
            print(f"\n🔴 ERRORS ({len(errors)}):")
            for issue in errors[:5]:  # Show first 5
                print(f"  • {issue.field}: {issue.message}")
                print(f"    💡 {issue.suggestion}")
        
        if warnings:
            print(f"\n🟡 WARNINGS ({len(warnings)}):")
            for issue in warnings[:5]:  # Show first 5
                print(f"  • {issue.field}: {issue.message}")
                print(f"    💡 {issue.suggestion}")
    
    def _generate_report(self, config_path: str) -> Dict:
        """Generate validation report."""
        
        return {
            "config_file": config_path,
            "valid": len(self.issues) == 0 or all(i.severity != "error" for i in self.issues),
            "servers": {
                "total": len(self.valid_servers) + len(self.invalid_servers),
                "valid": len(self.valid_servers),
                "invalid": len(self.invalid_servers)
            },
            "issues": {
                "errors": len([i for i in self.issues if i.severity == "error"]),
                "warnings": len([i for i in self.issues if i.severity == "warning"]),
                "details": [
                    {
                        "severity": i.severity,
                        "field": i.field,
                        "message": i.message,
                        "suggestion": i.suggestion
                    }
                    for i in self.issues
                ]
            },
            "valid_servers": self.valid_servers,
            "invalid_servers": self.invalid_servers
        }
    
    def generate_valid_config(self, format: ConfigFormat, servers: Dict) -> Dict:
        """Generate a valid configuration for the specified format."""
        
        if format == ConfigFormat.CLAUDE_DESKTOP:
            return {
                "mcpServers": servers
            }
        elif format == ConfigFormat.CURSOR:
            return {
                "mcp": {
                    "servers": servers
                }
            }
        elif format == ConfigFormat.CLINE:
            server_list = []
            for name, config in servers.items():
                config['name'] = name
                server_list.append(config)
            return {
                "servers": server_list
            }
        else:
            return servers


def main():
    """Run configuration validator."""
    
    if len(sys.argv) < 2:
        # Try to find common config files
        common_paths = [
            os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json"),
            os.path.expanduser("~/.cursor/config.json"),
            os.path.expanduser("~/.cline/config.json"),
            "./mcp_config.json"
        ]
        
        print("Usage: python config_validator.py <config_file>")
        print("\nSearching for common config files...")
        
        for path in common_paths:
            if os.path.exists(path):
                print(f"  Found: {path}")
                validator = ConfigurationValidator()
                report = validator.validate_config_file(path)
                
                # Save report
                report_file = f"config_validation_{Path(path).stem}.json"
                with open(report_file, "w") as f:
                    json.dump(report, f, indent=2)
                print(f"\nReport saved to {report_file}")
        
        return 0
    
    config_path = sys.argv[1]
    
    validator = ConfigurationValidator()
    report = validator.validate_config_file(config_path)
    
    # Save report
    report_file = f"config_validation_{Path(config_path).stem}.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport saved to {report_file}")
    
    return 0 if report['valid'] else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)