"""
Sandbox configuration and templates.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


class SandboxProvider(Enum):
    """Supported sandbox providers."""
    LOCAL = "local"
    DOCKER = "docker"
    MODAL = "modal"


@dataclass
class ResourceLimits:
    """Resource limits for sandboxes."""
    cpu: float = 2.0  # CPU cores
    memory: int = 2048  # Memory in MB
    disk: int = 10240  # Disk in MB
    timeout: int = 3600  # Timeout in seconds
    max_processes: int = 100
    max_open_files: int = 1024


@dataclass
class NetworkConfig:
    """Network configuration for sandboxes."""
    enable_network: bool = True
    allowed_hosts: List[str] = field(default_factory=list)
    blocked_hosts: List[str] = field(default_factory=list)
    port_mappings: Dict[int, int] = field(default_factory=dict)
    dns_servers: List[str] = field(default_factory=lambda: ["8.8.8.8", "8.8.4.4"])


@dataclass
class VolumeMount:
    """Volume mount configuration."""
    host_path: str
    container_path: str
    read_only: bool = False


@dataclass
class SandboxConfig:
    """Base sandbox configuration."""
    name: str
    provider: SandboxProvider = SandboxProvider.LOCAL
    image: str = "python:3.11"
    resources: ResourceLimits = field(default_factory=ResourceLimits)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    environment: Dict[str, str] = field(default_factory=dict)
    volumes: List[VolumeMount] = field(default_factory=list)
    packages: List[str] = field(default_factory=list)
    entrypoint: Optional[List[str]] = None
    working_dir: str = "/workspace"
    user: Optional[str] = None
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class ModalSandboxConfig(SandboxConfig):
    """Modal-specific sandbox configuration."""
    provider: SandboxProvider = SandboxProvider.MODAL
    modal_stub_name: str = "mcp-reliability-sandbox"
    modal_function_name: str = "sandbox_executor"
    modal_gpu: Optional[str] = None  # e.g., "t4", "a10g"
    modal_region: Optional[str] = None  # e.g., "us-east-1"
    modal_timeout: int = 3600
    modal_retries: int = 3
    modal_keep_warm: int = 0  # Keep warm instances
    modal_concurrency_limit: int = 10
    modal_secrets: List[str] = field(default_factory=list)


# Predefined sandbox templates
SANDBOX_TEMPLATES = {
    "python_default": SandboxConfig(
        name="python-default",
        provider=SandboxProvider.LOCAL,
        image="python:3.11",
        packages=["requests", "pytest", "numpy", "pandas"],
        environment={"PYTHONUNBUFFERED": "1"}
    ),
    
    "mcp_testing": SandboxConfig(
        name="mcp-testing",
        provider=SandboxProvider.DOCKER,
        image="python:3.11",
        packages=["mcp", "pytest", "pytest-asyncio", "httpx"],
        environment={
            "PYTHONUNBUFFERED": "1",
            "MCP_ENV": "testing"
        },
        resources=ResourceLimits(cpu=4.0, memory=4096)
    ),
    
    "chaos_engineering": SandboxConfig(
        name="chaos-engineering",
        provider=SandboxProvider.MODAL,
        image="python:3.11",
        packages=["chaos-toolkit", "pytest", "toxiproxy-python"],
        environment={
            "CHAOS_ENABLED": "true",
            "PYTHONUNBUFFERED": "1"
        },
        resources=ResourceLimits(cpu=8.0, memory=8192, timeout=7200)
    ),
    
    "nodejs_mcp": SandboxConfig(
        name="nodejs-mcp",
        provider=SandboxProvider.DOCKER,
        image="node:18",
        packages=[],  # npm packages handled differently
        environment={
            "NODE_ENV": "testing"
        }
    ),
    
    "performance_testing": SandboxConfig(
        name="performance-testing",
        provider=SandboxProvider.MODAL,
        image="python:3.11",
        packages=["locust", "pytest-benchmark", "memory-profiler"],
        resources=ResourceLimits(cpu=16.0, memory=32768, timeout=14400)
    )
}


def get_sandbox_template(template_name: str) -> SandboxConfig:
    """Get a predefined sandbox template."""
    if template_name not in SANDBOX_TEMPLATES:
        raise ValueError(f"Unknown template: {template_name}. Available: {list(SANDBOX_TEMPLATES.keys())}")
    
    # Return a copy to avoid mutations
    template = SANDBOX_TEMPLATES[template_name]
    return SandboxConfig(
        name=template.name,
        provider=template.provider,
        image=template.image,
        resources=ResourceLimits(**template.resources.__dict__),
        network=NetworkConfig(**template.network.__dict__),
        environment=template.environment.copy(),
        volumes=template.volumes.copy(),
        packages=template.packages.copy(),
        entrypoint=template.entrypoint,
        working_dir=template.working_dir,
        user=template.user,
        labels=template.labels.copy()
    )


def create_custom_template(
    name: str,
    base_template: str = "python_default",
    **overrides
) -> SandboxConfig:
    """Create a custom template based on an existing one."""
    config = get_sandbox_template(base_template)
    config.name = name
    
    # Apply overrides
    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)
    
    return config