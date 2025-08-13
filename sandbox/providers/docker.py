"""
Docker sandbox provider for containerized isolation.
"""

import asyncio
import logging
from typing import List, Dict, Optional

from .base import BaseSandbox, SandboxResult
from ..config import SandboxConfig


logger = logging.getLogger(__name__)


class DockerSandbox(BaseSandbox):
    """Docker-based sandbox for container isolation."""
    
    def __init__(self, sandbox_id: str, config: SandboxConfig):
        super().__init__(sandbox_id, config)
        self.container_id = None
        self.docker_client = None
    
    async def setup(self):
        """Set up Docker container sandbox."""
        try:
            import docker
            self.docker_client = docker.from_env()
            
            # Create container
            container = self.docker_client.containers.create(
                image=self.config.image,
                name=f"mcp_sandbox_{self.sandbox_id}",
                environment=self.config.environment,
                mem_limit=f"{self.config.resources.memory}m",
                cpu_quota=int(self.config.resources.cpu * 100000),
                detach=True,
                stdin_open=True,
                tty=True
            )
            
            self.container_id = container.id
            container.start()
            
            logger.info(f"Started Docker container: {self.container_id[:12]}")
            self.is_ready = True
            
            # Install packages
            if self.config.packages:
                await self.install_packages(self.config.packages)
                
        except ImportError:
            logger.error("Docker SDK not installed. Install with: pip install docker")
            raise
        except Exception as e:
            logger.error(f"Failed to create Docker sandbox: {e}")
            raise
    
    async def execute(
        self,
        command: List[str],
        environment: Optional[Dict[str, str]] = None,
        working_dir: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> SandboxResult:
        """Execute command in Docker container."""
        if not self.is_ready or not self.container_id:
            raise RuntimeError(f"Sandbox {self.sandbox_id} is not ready")
        
        try:
            container = self.docker_client.containers.get(self.container_id)
            
            # Execute command
            result = container.exec_run(
                cmd=command,
                environment=environment,
                workdir=working_dir or self.config.working_dir,
                demux=True
            )
            
            stdout = result.output[0].decode('utf-8') if result.output[0] else ""
            stderr = result.output[1].decode('utf-8') if result.output[1] else ""
            
            return SandboxResult(
                exit_code=result.exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=0,  # Docker doesn't provide duration
                metadata={"container_id": self.container_id[:12]}
            )
            
        except Exception as e:
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_seconds=0,
                metadata={"error": str(e)}
            )
    
    async def cleanup(self):
        """Clean up Docker container."""
        if self.container_id and self.docker_client:
            try:
                container = self.docker_client.containers.get(self.container_id)
                container.stop(timeout=10)
                container.remove()
                logger.info(f"Cleaned up Docker container: {self.container_id[:12]}")
            except Exception as e:
                logger.error(f"Failed to clean up container: {e}")
        
        self.is_ready = False