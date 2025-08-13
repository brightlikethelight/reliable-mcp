"""
Local sandbox provider for testing without external dependencies.
"""

import asyncio
import logging
import os
import subprocess
import tempfile
import time
from typing import List, Dict, Optional

from .base import BaseSandbox, SandboxResult
from ..config import SandboxConfig


logger = logging.getLogger(__name__)


class LocalSandbox(BaseSandbox):
    """Local sandbox using subprocess isolation."""
    
    def __init__(self, sandbox_id: str, config: SandboxConfig):
        super().__init__(sandbox_id, config)
        self.temp_dir = None
    
    async def setup(self):
        """Set up local sandbox environment."""
        # Create temporary directory for isolation
        self.temp_dir = tempfile.mkdtemp(prefix=f"mcp_sandbox_{self.sandbox_id}_")
        logger.info(f"Created local sandbox at: {self.temp_dir}")
        
        # Set up environment
        self.metadata["temp_dir"] = self.temp_dir
        self.is_ready = True
        
        # Install packages if specified
        if self.config.packages:
            await self.install_packages(self.config.packages)
    
    async def execute(
        self,
        command: List[str],
        environment: Optional[Dict[str, str]] = None,
        working_dir: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> SandboxResult:
        """Execute command locally with isolation."""
        if not self.is_ready:
            raise RuntimeError(f"Sandbox {self.sandbox_id} is not ready")
        
        # Prepare environment
        env = os.environ.copy()
        env.update(self.config.environment)
        if environment:
            env.update(environment)
        
        # Set working directory
        if not working_dir:
            working_dir = self.temp_dir
        
        # Set timeout
        if not timeout:
            timeout = self.config.resources.timeout
        
        start_time = time.time()
        
        try:
            # Execute command
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=working_dir
            )
            
            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                exit_code = process.returncode
            except asyncio.TimeoutError:
                process.kill()
                stdout, stderr = await process.communicate()
                exit_code = -1
                stderr = b"Command timed out\n" + (stderr or b"")
            
            duration = time.time() - start_time
            
            return SandboxResult(
                exit_code=exit_code,
                stdout=stdout.decode('utf-8', errors='replace') if stdout else "",
                stderr=stderr.decode('utf-8', errors='replace') if stderr else "",
                duration_seconds=duration,
                metadata={"sandbox_id": self.sandbox_id}
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_seconds=duration,
                metadata={"sandbox_id": self.sandbox_id, "error": str(e)}
            )
    
    async def cleanup(self):
        """Clean up local sandbox."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                import shutil
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up local sandbox: {self.temp_dir}")
            except Exception as e:
                logger.error(f"Failed to clean up sandbox {self.sandbox_id}: {e}")
        
        self.is_ready = False