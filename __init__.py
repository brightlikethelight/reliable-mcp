"""
MCP Reliability Lab - Comprehensive Testing Platform for MCP Servers
Built for Modal + Cognition + AWS Hackathon 2025
"""

__version__ = "1.0.0"
__author__ = "Bright Liu"

# Core modules
from .mcp_client import MCPClient
from .config import SERVERS, TEST_DIR

# Testing modules  
from .security_scanner import MCPSecurityScanner
from .performance_tester import PerformanceTester
from .chaos_tester import ChaosTester

__all__ = [
    "MCPClient",
    "SERVERS",
    "TEST_DIR", 
    "MCPSecurityScanner",
    "PerformanceTester",
    "ChaosTester",
]