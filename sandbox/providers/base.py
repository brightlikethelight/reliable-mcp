"""
Base sandbox provider interface.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional, Any

from ..config import SandboxConfig


logger = logging.getLogger(__name__)


@dataclass
class SandboxResult:
    """Result from sandbox execution."""
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    metadata: Dict[str, Any] = None


class BaseSandbox(ABC):
    """Base class for sandbox providers."""
    
    def __init__(self, sandbox_id: str, config: SandboxConfig):
        self.sandbox_id = sandbox_id
        self.config = config
        self.created_at = datetime.now()
        self.is_ready = False
        self.metadata: Dict[str, Any] = {}
    
    @abstractmethod
    async def setup(self):
        """Set up the sandbox environment."""
        pass
    
    @abstractmethod
    async def execute(
        self,
        command: List[str],
        environment: Optional[Dict[str, str]] = None,
        working_dir: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> SandboxResult:
        """Execute a command in the sandbox."""
        pass
    
    @abstractmethod
    async def cleanup(self):
        """Clean up sandbox resources."""
        pass
    
    async def write_file(self, path: str, content: str):
        """Write a file in the sandbox."""
        # Default implementation using echo
        escaped_content = content.replace("'", "'\\''")
        command = ["sh", "-c", f"echo '{escaped_content}' > {path}"]
        return await self.execute(command)
    
    async def read_file(self, path: str) -> str:
        """Read a file from the sandbox."""
        result = await self.execute(["cat", path])
        if result.exit_code != 0:
            raise IOError(f"Failed to read file {path}: {result.stderr}")
        return result.stdout
    
    async def file_exists(self, path: str) -> bool:
        """Check if a file exists in the sandbox."""
        result = await self.execute(["test", "-f", path])
        return result.exit_code == 0
    
    async def list_directory(self, path: str = ".") -> List[str]:
        """List directory contents."""
        result = await self.execute(["ls", "-la", path])
        if result.exit_code != 0:
            raise IOError(f"Failed to list directory {path}: {result.stderr}")
        
        lines = result.stdout.strip().split("\n")
        # Skip the total line and parse filenames
        files = []
        for line in lines[1:]:  # Skip "total" line
            parts = line.split()
            if len(parts) >= 9:
                filename = " ".join(parts[8:])
                if filename not in [".", ".."]:
                    files.append(filename)
        return files
    
    async def install_packages(self, packages: List[str]):
        """Install packages in the sandbox."""
        if not packages:
            return
        
        # Detect package manager based on image
        if "python" in self.config.image:
            command = ["pip", "install"] + packages
        elif "node" in self.config.image:
            command = ["npm", "install", "-g"] + packages
        elif "ubuntu" in self.config.image or "debian" in self.config.image:
            # Update first, then install
            await self.execute(["apt-get", "update"])
            command = ["apt-get", "install", "-y"] + packages
        else:
            logger.warning(f"Unknown image type for package installation: {self.config.image}")
            return
        
        result = await self.execute(command, timeout=300)
        if result.exit_code != 0:
            logger.error(f"Failed to install packages: {result.stderr}")
            raise RuntimeError(f"Package installation failed: {result.stderr}")
    
    async def deploy_mcp_server(
        self,
        server_path: str,
        config: Dict[str, Any],
        port: int = 8000
    ) -> str:
        """Deploy an MCP server in the sandbox."""
        # This is a placeholder - actual implementation depends on provider
        logger.warning(f"MCP server deployment not implemented for {self.__class__.__name__}")
        return f"http://localhost:{port}"
    
    def get_info(self) -> Dict[str, Any]:
        """Get sandbox information."""
        return {
            "sandbox_id": self.sandbox_id,
            "provider": self.config.provider.value,
            "image": self.config.image,
            "created_at": self.created_at.isoformat(),
            "is_ready": self.is_ready,
            "resources": {
                "cpu": self.config.resources.cpu,
                "memory": self.config.resources.memory,
                "timeout": self.config.resources.timeout
            },
            "metadata": self.metadata
        }