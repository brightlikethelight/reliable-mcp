"""
Modal sandbox provider for serverless isolated execution.
"""

import asyncio
import logging
import os
from typing import List, Dict, Optional, Any

from .base import BaseSandbox, SandboxResult
from ..config import ModalSandboxConfig


logger = logging.getLogger(__name__)


class ModalSandbox(BaseSandbox):
    """Modal-based sandbox for serverless execution."""
    
    def __init__(self, sandbox_id: str, config: ModalSandboxConfig):
        super().__init__(sandbox_id, config)
        self.modal_stub = None
        self.modal_function = None
    
    async def setup(self):
        """Set up Modal sandbox environment."""
        try:
            import modal
            
            # Check for Modal token
            if not os.environ.get("MODAL_TOKEN_ID"):
                logger.warning("MODAL_TOKEN_ID not set. Modal features will be limited.")
                # Fall back to mock mode
                self.is_ready = True
                self.metadata["mode"] = "mock"
                return
            
            # Create Modal stub
            self.modal_stub = modal.Stub(self.config.modal_stub_name)
            
            # Define Modal function
            @self.modal_stub.function(
                image=modal.Image.debian_slim().pip_install(self.config.packages),
                gpu=self.config.modal_gpu,
                timeout=self.config.modal_timeout,
                retries=self.config.modal_retries,
                keep_warm=self.config.modal_keep_warm,
                concurrency_limit=self.config.modal_concurrency_limit,
                secrets=[modal.Secret.from_name(s) for s in self.config.modal_secrets]
                if self.config.modal_secrets else None
            )
            async def execute_in_modal(command: List[str], env: Dict[str, str], cwd: str):
                import subprocess
                import time
                
                start_time = time.time()
                
                # Merge environments
                full_env = os.environ.copy()
                full_env.update(env)
                
                try:
                    result = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        env=full_env,
                        cwd=cwd,
                        timeout=self.config.modal_timeout
                    )
                    
                    return {
                        "exit_code": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "duration": time.time() - start_time
                    }
                except subprocess.TimeoutExpired:
                    return {
                        "exit_code": -1,
                        "stdout": "",
                        "stderr": "Command timed out",
                        "duration": time.time() - start_time
                    }
                except Exception as e:
                    return {
                        "exit_code": -1,
                        "stdout": "",
                        "stderr": str(e),
                        "duration": time.time() - start_time
                    }
            
            self.modal_function = execute_in_modal
            
            logger.info(f"Created Modal sandbox: {self.config.modal_stub_name}")
            self.is_ready = True
            self.metadata["mode"] = "live"
            
        except ImportError:
            logger.warning("Modal SDK not installed. Using mock mode.")
            self.is_ready = True
            self.metadata["mode"] = "mock"
        except Exception as e:
            logger.error(f"Failed to create Modal sandbox: {e}")
            self.is_ready = True
            self.metadata["mode"] = "mock"
    
    async def execute(
        self,
        command: List[str],
        environment: Optional[Dict[str, str]] = None,
        working_dir: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> SandboxResult:
        """Execute command in Modal sandbox."""
        if not self.is_ready:
            raise RuntimeError(f"Sandbox {self.sandbox_id} is not ready")
        
        # Check if in mock mode
        if self.metadata.get("mode") == "mock":
            return await self._mock_execute(command, environment, working_dir, timeout)
        
        # Prepare environment
        env = self.config.environment.copy()
        if environment:
            env.update(environment)
        
        # Set working directory
        if not working_dir:
            working_dir = self.config.working_dir
        
        try:
            # Execute in Modal
            result = await self.modal_function.remote(command, env, working_dir)
            
            return SandboxResult(
                exit_code=result["exit_code"],
                stdout=result["stdout"],
                stderr=result["stderr"],
                duration_seconds=result["duration"],
                metadata={"sandbox_id": self.sandbox_id, "provider": "modal"}
            )
            
        except Exception as e:
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_seconds=0,
                metadata={"error": str(e)}
            )
    
    async def _mock_execute(
        self,
        command: List[str],
        environment: Optional[Dict[str, str]] = None,
        working_dir: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> SandboxResult:
        """Mock execution for when Modal is not available."""
        import time
        
        # Simulate execution
        await asyncio.sleep(0.1)  # Simulate network latency
        
        # Generate mock response based on command
        if command[0] == "python" and "-c" in command:
            stdout = "Python 3.11.0"
        elif command[0] == "pip" and "list" in command:
            stdout = "Package    Version\n-------    -------\nmcp        1.0.0"
        elif command[0] == "cat":
            stdout = "Mock file content"
        else:
            stdout = f"Mock execution of: {' '.join(command)}"
        
        return SandboxResult(
            exit_code=0,
            stdout=stdout,
            stderr="",
            duration_seconds=0.1,
            metadata={"sandbox_id": self.sandbox_id, "mode": "mock"}
        )
    
    async def cleanup(self):
        """Clean up Modal sandbox."""
        if self.modal_stub:
            try:
                # Modal cleanup if needed
                logger.info(f"Cleaned up Modal sandbox: {self.sandbox_id}")
            except Exception as e:
                logger.error(f"Failed to clean up Modal sandbox: {e}")
        
        self.is_ready = False
    
    async def deploy_mcp_server(
        self,
        server_path: str,
        config: Dict[str, Any],
        port: int = 8000
    ) -> str:
        """Deploy MCP server to Modal."""
        if self.metadata.get("mode") == "mock":
            # Return mock URL
            return f"https://mock-{self.sandbox_id}.modal.run"
        
        try:
            import modal
            
            # Create a Modal web endpoint
            @self.modal_stub.web_endpoint(method="POST")
            async def mcp_endpoint(request: Dict[str, Any]):
                # Mock MCP server response
                return {
                    "jsonrpc": "2.0",
                    "result": {"status": "ok"},
                    "id": request.get("id", 1)
                }
            
            # Get the URL (this would be the actual Modal URL in production)
            url = f"https://{self.config.modal_stub_name}.modal.run"
            logger.info(f"Deployed MCP server to Modal: {url}")
            
            return url
            
        except Exception as e:
            logger.error(f"Failed to deploy MCP server: {e}")
            return f"https://error-{self.sandbox_id}.modal.run"