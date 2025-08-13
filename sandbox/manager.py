"""
Sandbox manager for orchestrating isolated execution environments.
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

from .config import (
    SandboxConfig, ModalSandboxConfig, SandboxProvider,
    ResourceLimits, get_sandbox_template
)
from .providers.base import BaseSandbox, SandboxResult


logger = logging.getLogger(__name__)


class SandboxManager:
    """Manages lifecycle of sandbox environments."""
    
    def __init__(
        self,
        default_provider: Union[SandboxProvider, str] = SandboxProvider.LOCAL,
        max_concurrent_sandboxes: int = 10,
        enable_metrics: bool = True,
        cleanup_on_exit: bool = True
    ):
        """Initialize sandbox manager."""
        if isinstance(default_provider, str):
            default_provider = SandboxProvider(default_provider)
        
        self.default_provider = default_provider
        self.max_concurrent_sandboxes = max_concurrent_sandboxes
        self.enable_metrics = enable_metrics
        self.cleanup_on_exit = cleanup_on_exit
        
        self.active_sandboxes: Dict[str, BaseSandbox] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent_sandboxes)
        self._metrics: Dict[str, Any] = {
            "sandboxes_created": 0,
            "sandboxes_destroyed": 0,
            "total_execution_time": 0,
            "errors": []
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        logger.info(f"SandboxManager initialized with provider: {self.default_provider}")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.cleanup_on_exit:
            await self.cleanup_all()
    
    @asynccontextmanager
    async def sandbox_context(self, config: Union[SandboxConfig, Dict[str, Any]]):
        """Context manager for sandbox lifecycle."""
        if isinstance(config, dict):
            config = self._dict_to_config(config)
        
        sandbox = None
        try:
            sandbox = await self.create_sandbox(config)
            yield sandbox
        finally:
            if sandbox:
                await self.destroy_sandbox(sandbox.sandbox_id)
    
    async def create_sandbox(
        self,
        config: Union[SandboxConfig, Dict[str, Any]],
        auto_setup: bool = True
    ) -> BaseSandbox:
        """Create a new sandbox."""
        async with self._semaphore:
            if isinstance(config, dict):
                config = self._dict_to_config(config)
            
            # Generate unique ID
            sandbox_id = f"{config.name}-{uuid.uuid4().hex[:8]}"
            
            # Create provider-specific sandbox
            sandbox = await self._create_provider_sandbox(sandbox_id, config)
            
            if auto_setup:
                await sandbox.setup()
            
            self.active_sandboxes[sandbox_id] = sandbox
            self._metrics["sandboxes_created"] += 1
            
            logger.info(f"Created sandbox: {sandbox_id} with provider: {config.provider}")
            return sandbox
    
    async def destroy_sandbox(self, sandbox_id: str):
        """Destroy a sandbox."""
        if sandbox_id not in self.active_sandboxes:
            logger.warning(f"Sandbox not found: {sandbox_id}")
            return
        
        sandbox = self.active_sandboxes[sandbox_id]
        
        try:
            await sandbox.cleanup()
            del self.active_sandboxes[sandbox_id]
            self._metrics["sandboxes_destroyed"] += 1
            logger.info(f"Destroyed sandbox: {sandbox_id}")
        except Exception as e:
            logger.error(f"Error destroying sandbox {sandbox_id}: {e}")
            self._metrics["errors"].append({
                "type": "destroy_error",
                "sandbox_id": sandbox_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    async def cleanup_all(self):
        """Clean up all active sandboxes."""
        logger.info(f"Cleaning up {len(self.active_sandboxes)} active sandboxes")
        
        tasks = []
        for sandbox_id in list(self.active_sandboxes.keys()):
            tasks.append(self.destroy_sandbox(sandbox_id))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_active_sandboxes(self) -> List[str]:
        """Get list of active sandbox IDs."""
        return list(self.active_sandboxes.keys())
    
    def get_sandbox(self, sandbox_id: str) -> Optional[BaseSandbox]:
        """Get a specific sandbox by ID."""
        return self.active_sandboxes.get(sandbox_id)
    
    def get_sandbox_template(self, template_name: str) -> SandboxConfig:
        """Get a predefined sandbox template."""
        return get_sandbox_template(template_name)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get sandbox manager metrics."""
        return self._metrics.copy()
    
    def _dict_to_config(self, config_dict: Dict[str, Any]) -> SandboxConfig:
        """Convert dictionary to SandboxConfig."""
        provider = config_dict.get("provider", self.default_provider)
        if isinstance(provider, str):
            provider = SandboxProvider(provider)
        
        # Handle Modal-specific config
        if provider == SandboxProvider.MODAL:
            return ModalSandboxConfig(
                name=config_dict.get("name", "sandbox"),
                provider=provider,
                image=config_dict.get("image", "python:3.11"),
                resources=self._dict_to_resources(config_dict.get("resources", {})),
                environment=config_dict.get("environment", {}),
                packages=config_dict.get("packages", []),
                modal_stub_name=config_dict.get("modal_stub_name", "mcp-sandbox"),
                modal_function_name=config_dict.get("modal_function_name", "executor"),
                modal_gpu=config_dict.get("modal_gpu"),
                modal_region=config_dict.get("modal_region"),
                modal_timeout=config_dict.get("modal_timeout", 3600),
                modal_retries=config_dict.get("modal_retries", 3)
            )
        
        # Default config
        return SandboxConfig(
            name=config_dict.get("name", "sandbox"),
            provider=provider,
            image=config_dict.get("image", "python:3.11"),
            resources=self._dict_to_resources(config_dict.get("resources", {})),
            environment=config_dict.get("environment", {}),
            packages=config_dict.get("packages", []),
            entrypoint=config_dict.get("entrypoint"),
            working_dir=config_dict.get("working_dir", "/workspace")
        )
    
    def _dict_to_resources(self, resources_dict: Dict[str, Any]) -> ResourceLimits:
        """Convert dictionary to ResourceLimits."""
        return ResourceLimits(
            cpu=resources_dict.get("cpu", 2.0),
            memory=resources_dict.get("memory", 2048),
            disk=resources_dict.get("disk", 10240),
            timeout=resources_dict.get("timeout", 3600),
            max_processes=resources_dict.get("max_processes", 100),
            max_open_files=resources_dict.get("max_open_files", 1024)
        )
    
    async def _create_provider_sandbox(
        self,
        sandbox_id: str,
        config: SandboxConfig
    ) -> BaseSandbox:
        """Create provider-specific sandbox."""
        
        if config.provider == SandboxProvider.LOCAL:
            from .providers.local import LocalSandbox
            return LocalSandbox(sandbox_id, config)
        
        elif config.provider == SandboxProvider.DOCKER:
            from .providers.docker import DockerSandbox
            return DockerSandbox(sandbox_id, config)
        
        elif config.provider == SandboxProvider.MODAL:
            from .providers.modal import ModalSandbox
            return ModalSandbox(sandbox_id, config)
        
        else:
            raise ValueError(f"Unsupported provider: {config.provider}")


class SandboxOrchestrator:
    """Orchestrates complex sandbox workflows."""
    
    def __init__(self, manager: SandboxManager):
        self.manager = manager
        self.workflows: Dict[str, Any] = {}
    
    async def run_parallel_sandboxes(
        self,
        configs: List[Union[SandboxConfig, Dict[str, Any]]],
        task_func: Any,
        *args,
        **kwargs
    ) -> List[Any]:
        """Run tasks in parallel sandboxes."""
        tasks = []
        
        for config in configs:
            async def run_in_sandbox(cfg):
                async with self.manager.sandbox_context(cfg) as sandbox:
                    return await task_func(sandbox, *args, **kwargs)
            
            tasks.append(run_in_sandbox(config))
        
        return await asyncio.gather(*tasks)
    
    async def run_sequential_pipeline(
        self,
        configs: List[Union[SandboxConfig, Dict[str, Any]]],
        pipeline_funcs: List[Any]
    ) -> List[Any]:
        """Run pipeline of tasks sequentially through sandboxes."""
        results = []
        previous_result = None
        
        for config, func in zip(configs, pipeline_funcs):
            async with self.manager.sandbox_context(config) as sandbox:
                result = await func(sandbox, previous_result)
                results.append(result)
                previous_result = result
        
        return results