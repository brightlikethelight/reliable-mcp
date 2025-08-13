#!/usr/bin/env python3
"""
Configuration module for MCP Reliability Lab.
Centralizes all configuration and eliminates hardcoded paths.
"""

import os
import tempfile
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_DIR = BASE_DIR / "databases"
LOGS_DIR = BASE_DIR / "logs"

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
DB_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Test directory - use system temp dir with fallback
def get_test_dir():
    """Get appropriate test directory for the platform."""
    # Try environment variable first
    if 'MCP_TEST_DIR' in os.environ:
        test_dir = Path(os.environ['MCP_TEST_DIR'])
        test_dir.mkdir(parents=True, exist_ok=True)
        return str(test_dir)
    
    # Use tempfile for cross-platform compatibility
    temp_base = Path(tempfile.gettempdir())
    test_dir = temp_base / "mcp-test"
    test_dir.mkdir(exist_ok=True)
    # Use realpath to resolve symlinks (important on macOS)
    return str(test_dir.resolve())

# Configuration
TEST_DIR = get_test_dir()

# Database paths
DATABASES = {
    'metrics': str(DB_DIR / 'mcp_metrics.db'),
    'test_results': str(DB_DIR / 'test_results.db'),
    'web_metrics': str(DB_DIR / 'web_metrics.db'),
    'leaderboard': str(DB_DIR / 'leaderboard.db'),
    'benchmarks': str(DB_DIR / 'benchmarks.db')
}

# Server configurations
SERVERS = {
    'filesystem': {
        'command': ['npx', '@modelcontextprotocol/server-filesystem'],
        'args': [str(TEST_DIR)],
        'path': str(TEST_DIR),
        'description': 'Local filesystem operations',
        'transport': 'stdio'
    },
    'github': {
        'command': ['npx', '@modelcontextprotocol/server-github'],
        'args': [],
        'env': {'GITHUB_TOKEN': os.environ.get('GITHUB_TOKEN', '')},
        'description': 'GitHub repository operations',
        'transport': 'stdio'
    },
    'postgresql': {
        'command': ['npx', '@henkey/postgres-mcp-server'],
        'args': [],
        'env': {
            'POSTGRES_HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
            'POSTGRES_PORT': os.environ.get('POSTGRES_PORT', '5432'),
            'POSTGRES_DB': os.environ.get('POSTGRES_DB', 'test_db'),
            'POSTGRES_USER': os.environ.get('POSTGRES_USER', 'postgres'),
            'POSTGRES_PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'postgres')
        },
        'description': 'PostgreSQL database management (17 tools)',
        'transport': 'stdio'
    },
    'slack': {
        'command': ['npx', '@modelcontextprotocol/server-slack'],
        'args': [],
        'env': {
            'SLACK_TOKEN': os.environ.get('SLACK_TOKEN', ''),
            'SLACK_WORKSPACE': os.environ.get('SLACK_WORKSPACE', '')
        },
        'description': 'Slack workspace communication',
        'transport': 'stdio'
    },
    'git': {
        'command': ['npx', '@modelcontextprotocol/server-git'],
        'args': ['.'],
        'description': 'Git repository operations',
        'transport': 'stdio'
    },
    'google-drive': {
        'command': ['npx', '@modelcontextprotocol/server-google-drive'],
        'args': [],
        'env': {
            'GOOGLE_CREDENTIALS': os.environ.get('GOOGLE_CREDENTIALS', '')
        },
        'description': 'Google Drive file management',
        'transport': 'stdio'
    },
    'puppeteer': {
        'command': ['npx', '@modelcontextprotocol/server-puppeteer'],
        'args': [],
        'description': 'Web browser automation',
        'transport': 'stdio'
    },
    'memory': {
        'command': ['npx', '@modelcontextprotocol/server-memory'],
        'args': [],
        'description': 'In-memory key-value storage',
        'transport': 'stdio'
    },
    'sqlite': {
        'command': ['npx', '@modelcontextprotocol/server-sqlite'],
        'args': [str(DB_DIR / 'test.db')],
        'description': 'SQLite database operations',
        'transport': 'stdio'
    },
    'brave-search': {
        'command': ['npx', '@modelcontextprotocol/server-brave-search'],
        'args': [],
        'env': {
            'BRAVE_API_KEY': os.environ.get('BRAVE_API_KEY', '')
        },
        'description': 'Brave search engine integration',
        'transport': 'stdio'
    }
}

# API Configuration
API_CONFIG = {
    'host': os.environ.get('MCP_LAB_HOST', '0.0.0.0'),
    'port': int(os.environ.get('MCP_LAB_PORT', 8000)),
    'reload': os.environ.get('MCP_LAB_ENV', 'development') == 'development'
}

# Test Configuration
TEST_CONFIG = {
    'default_timeout': 30,  # seconds
    'retry_attempts': 3,
    'retry_delay': 1,  # seconds
}

# Benchmark Configuration
BENCHMARK_CONFIG = {
    'default_duration': 30,  # seconds
    'default_workload': 'real_world_mix',
    'warmup_operations': 10,
    'outlier_percentile': 10  # Remove top/bottom 10%
}

# Logging Configuration
LOG_CONFIG = {
    'level': os.environ.get('LOG_LEVEL', 'INFO'),
    'file': str(LOGS_DIR / 'mcp_lab.log'),
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
}

def get_config():
    """Get complete configuration dictionary."""
    return {
        'base_dir': str(BASE_DIR),
        'test_dir': TEST_DIR,
        'databases': DATABASES,
        'servers': SERVERS,
        'api': API_CONFIG,
        'test': TEST_CONFIG,
        'benchmark': BENCHMARK_CONFIG,
        'log': LOG_CONFIG
    }

# Export commonly used values
__all__ = [
    'BASE_DIR',
    'TEST_DIR',
    'DATABASES',
    'SERVERS',
    'API_CONFIG',
    'TEST_CONFIG',
    'BENCHMARK_CONFIG',
    'LOG_CONFIG',
    'get_config',
    'get_test_dir'
]