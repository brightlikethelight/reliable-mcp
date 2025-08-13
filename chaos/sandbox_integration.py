"""Integration between chaos engineering and Modal sandboxes."""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from opentelemetry import trace, metrics

from ..sandbox import SandboxManager, get_sandbox_template
from ..core import MCPServerWrapper
from .config import (
    ChaosExperimentConfig, NetworkFaultConfig, ResourceFaultConfig,
    FaultConfig, FaultType
)
from .orchestrator import ChaosOrchestrator, ChaosResult
from .monitors import SystemHealthMonitor, FaultMonitor


logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Metrics
sandbox_chaos_experiments = meter.create_counter(
    "chaos.sandbox_experiments",
    description="Number of chaos experiments in sandboxes"
)
sandbox_fault_injections = meter.create_counter(
    "chaos.sandbox_fault_injections",
    description="Number of fault injections in sandboxes"
)


class SandboxChaosOrchestrator:
    """Orchestrates chaos experiments within Modal sandboxes."""
    
    def __init__(self, sandbox_manager: SandboxManager):
        self.sandbox_manager = sandbox_manager
        self.chaos_orchestrator = ChaosOrchestrator()
        self.active_experiments: Dict[str, Dict[str, Any]] = {}
        
    async def run_chaos_in_sandbox(
        self,
        experiment_config: ChaosExperimentConfig,
        sandbox_template: str = "chaos_engineering",
        mcp_server_path: Optional[str] = None,
        mcp_server_config: Optional[Dict[str, Any]] = None
    ) -> ChaosResult:
        """Run chaos experiment in an isolated Modal sandbox."""
        
        span = tracer.start_span("sandbox_chaos_experiment")
        experiment_id = f"sandbox_chaos_{datetime.now().timestamp()}"
        
        try:
            # Get sandbox configuration
            sandbox_config = get_sandbox_template(sandbox_template)
            
            # Create sandbox with chaos tools
            async with self.sandbox_manager.sandbox_context(sandbox_config) as sandbox:
                logger.info(f"Created chaos sandbox: {sandbox.sandbox_id}")
                span.set_attribute("sandbox.id", sandbox.sandbox_id)
                
                # Deploy MCP server if provided
                server_url = None
                if mcp_server_path:
                    server_url = await sandbox.deploy_mcp_server(
                        mcp_server_path,
                        mcp_server_config or {},
                        port=8000
                    )
                    logger.info(f"Deployed MCP server at: {server_url}")
                    span.set_attribute("mcp.server_url", server_url)
                
                # Install chaos engineering tools
                await self._setup_chaos_tools(sandbox)
                
                # Run experiment
                result = await self._run_experiment_in_sandbox(
                    sandbox,
                    experiment_config,
                    server_url
                )
                
                # Collect artifacts
                artifacts = await self._collect_chaos_artifacts(sandbox)
                result.metrics["artifacts"] = artifacts
                
                sandbox_chaos_experiments.add(1, {
                    "template": sandbox_template,
                    "status": result.status
                })
                
                return result
                
        except Exception as e:
            logger.error(f"Sandbox chaos experiment failed: {e}")
            span.record_exception(e)
            raise
        finally:
            span.end()
    
    async def run_parallel_chaos_experiments(
        self,
        experiments: List[ChaosExperimentConfig],
        sandbox_template: str = "chaos_engineering",
        max_concurrent: int = 10
    ) -> List[ChaosResult]:
        """Run multiple chaos experiments in parallel sandboxes."""
        
        logger.info(f"Running {len(experiments)} parallel chaos experiments")
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def run_with_limit(exp_config):
            async with semaphore:
                return await self.run_chaos_in_sandbox(
                    exp_config,
                    sandbox_template
                )
        
        # Run experiments in parallel
        tasks = [run_with_limit(exp) for exp in experiments]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Experiment {i} failed: {result}")
                # Create failure result
                failure_result = ChaosResult(
                    experiment_id=f"failed_{i}",
                    status="failed",
                    errors=[str(result)]
                )
                processed_results.append(failure_result)
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def test_mcp_server_resilience(
        self,
        mcp_server_path: str,
        fault_scenarios: List[Dict[str, Any]],
        sandbox_template: str = "python_default"
    ) -> Dict[str, Any]:
        """Test MCP server resilience against various fault scenarios."""
        
        logger.info(f"Testing MCP server resilience with {len(fault_scenarios)} scenarios")
        
        results = {
            "server_path": mcp_server_path,
            "total_scenarios": len(fault_scenarios),
            "passed": 0,
            "failed": 0,
            "scenario_results": []
        }
        
        for scenario in fault_scenarios:
            # Create experiment config from scenario
            experiment_config = self._create_experiment_from_scenario(scenario)
            
            # Run chaos test
            try:
                result = await self.run_chaos_in_sandbox(
                    experiment_config,
                    sandbox_template,
                    mcp_server_path,
                    scenario.get("server_config", {})
                )
                
                # Check if server survived
                survived = result.status == "completed" and not result.safety_triggered
                
                scenario_result = {
                    "name": scenario.get("name", "Unknown"),
                    "survived": survived,
                    "experiment_id": result.experiment_id,
                    "faults_injected": result.successful_faults,
                    "errors": result.errors
                }
                
                if survived:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                
                results["scenario_results"].append(scenario_result)
                
            except Exception as e:
                logger.error(f"Scenario {scenario.get('name')} failed: {e}")
                results["failed"] += 1
                results["scenario_results"].append({
                    "name": scenario.get("name", "Unknown"),
                    "survived": False,
                    "error": str(e)
                })
        
        # Calculate resilience score
        results["resilience_score"] = results["passed"] / max(results["total_scenarios"], 1)
        
        return results
    
    async def _setup_chaos_tools(self, sandbox) -> None:
        """Install chaos engineering tools in the sandbox."""
        
        # Install required packages
        packages = [
            "chaos-toolkit",
            "chaostoolkit-kubernetes",
            "toxiproxy-python",
            "locust"
        ]
        
        for package in packages:
            try:
                result = await sandbox.execute([
                    "pip", "install", "--quiet", package
                ])
                if result.exit_code == 0:
                    logger.debug(f"Installed {package} in sandbox")
            except Exception as e:
                logger.warning(f"Failed to install {package}: {e}")
        
        # Setup network tools (tc, iptables simulation)
        await sandbox.execute([
            "apt-get", "update", "-qq"
        ])
        
        await sandbox.execute([
            "apt-get", "install", "-qq", "-y",
            "iproute2", "iptables", "stress-ng"
        ])
    
    async def _run_experiment_in_sandbox(
        self,
        sandbox,
        config: ChaosExperimentConfig,
        server_url: Optional[str] = None
    ) -> ChaosResult:
        """Execute chaos experiment within the sandbox."""
        
        # Create health monitor for the sandbox
        health_monitor = SystemHealthMonitor()
        await health_monitor.start_monitoring()
        
        try:
            # If MCP server is deployed, create wrapper
            mcp_wrapper = None
            if server_url:
                mcp_wrapper = MCPServerWrapper(
                    server_path="",  # Already deployed
                    server_type="http",
                    server_url=server_url
                )
                await mcp_wrapper.connect()
            
            # Inject faults in the sandbox
            for fault_config in config.faults:
                await self._inject_sandbox_fault(sandbox, fault_config)
            
            # Run the experiment
            result = await self.chaos_orchestrator.run_experiment(
                config,
                sandbox_id=sandbox.sandbox_id
            )
            
            # Test MCP server if available
            if mcp_wrapper:
                try:
                    # Test basic functionality during chaos
                    response = await mcp_wrapper.call_tool(
                        "test_tool",
                        {"input": "chaos_test"}
                    )
                    result.metrics["mcp_test_success"] = True
                    result.metrics["mcp_response"] = response
                except Exception as e:
                    result.metrics["mcp_test_success"] = False
                    result.metrics["mcp_error"] = str(e)
                finally:
                    await mcp_wrapper.disconnect()
            
            return result
            
        finally:
            await health_monitor.stop_monitoring()
    
    async def _inject_sandbox_fault(
        self,
        sandbox,
        fault_config: FaultConfig
    ) -> None:
        """Inject a fault within the sandbox environment."""
        
        sandbox_fault_injections.add(1, {"fault_type": fault_config.type})
        
        if isinstance(fault_config, NetworkFaultConfig):
            await self._inject_network_fault_sandbox(sandbox, fault_config)
        elif isinstance(fault_config, ResourceFaultConfig):
            await self._inject_resource_fault_sandbox(sandbox, fault_config)
        else:
            logger.warning(f"Unsupported fault type for sandbox: {fault_config.type}")
    
    async def _inject_network_fault_sandbox(
        self,
        sandbox,
        config: NetworkFaultConfig
    ) -> None:
        """Inject network fault in sandbox."""
        
        # Use tc (traffic control) for network simulation
        if config.latency_ms:
            await sandbox.execute([
                "tc", "qdisc", "add", "dev", "lo", "root", "netem",
                "delay", f"{config.latency_ms}ms"
            ])
        
        if config.loss_percentage:
            await sandbox.execute([
                "tc", "qdisc", "add", "dev", "lo", "root", "netem",
                "loss", f"{config.loss_percentage}%"
            ])
        
        if config.bandwidth_limit_mbps:
            await sandbox.execute([
                "tc", "qdisc", "add", "dev", "lo", "root", "tbf",
                "rate", f"{config.bandwidth_limit_mbps}mbit",
                "burst", "32kbit", "latency", "400ms"
            ])
    
    async def _inject_resource_fault_sandbox(
        self,
        sandbox,
        config: ResourceFaultConfig
    ) -> None:
        """Inject resource pressure in sandbox."""
        
        # Use stress-ng for resource pressure
        if config.resource_type == "cpu" and config.cpu_cores:
            await sandbox.execute([
                "stress-ng",
                "--cpu", str(config.cpu_cores),
                "--cpu-load", str(config.cpu_percentage or 80),
                "--timeout", f"{config.duration}s",
                "&"  # Run in background
            ])
        
        elif config.resource_type == "memory" and config.memory_mb:
            await sandbox.execute([
                "stress-ng",
                "--vm", "1",
                "--vm-bytes", f"{config.memory_mb}M",
                "--timeout", f"{config.duration}s",
                "&"
            ])
        
        elif config.resource_type == "disk" and config.disk_size_mb:
            await sandbox.execute([
                "stress-ng",
                "--hdd", "1",
                "--hdd-bytes", f"{config.disk_size_mb}M",
                "--timeout", f"{config.duration}s",
                "&"
            ])
    
    async def _collect_chaos_artifacts(self, sandbox) -> Dict[str, Any]:
        """Collect artifacts from chaos experiment."""
        
        artifacts = {}
        
        # Collect system logs
        try:
            result = await sandbox.execute(["dmesg", "-T", "|", "tail", "-100"])
            artifacts["system_logs"] = result.stdout
        except Exception as e:
            logger.warning(f"Failed to collect system logs: {e}")
        
        # Collect network statistics
        try:
            result = await sandbox.execute(["netstat", "-s"])
            artifacts["network_stats"] = result.stdout
        except Exception as e:
            logger.warning(f"Failed to collect network stats: {e}")
        
        # Collect process information
        try:
            result = await sandbox.execute(["ps", "aux", "--sort=-pcpu", "|", "head", "-20"])
            artifacts["top_processes"] = result.stdout
        except Exception as e:
            logger.warning(f"Failed to collect process info: {e}")
        
        return artifacts
    
    def _create_experiment_from_scenario(
        self,
        scenario: Dict[str, Any]
    ) -> ChaosExperimentConfig:
        """Create experiment configuration from scenario definition."""
        
        # Convert scenario to experiment config
        faults = []
        
        for fault_def in scenario.get("faults", []):
            fault_type = fault_def.get("type")
            
            if fault_type == "network_latency":
                fault = NetworkFaultConfig(
                    type=FaultType.NETWORK_LATENCY,
                    name=fault_def.get("name", "Network Latency"),
                    network_type="latency",
                    latency_ms=fault_def.get("latency_ms", 100),
                    duration=fault_def.get("duration", 60)
                )
            elif fault_type == "cpu_pressure":
                fault = ResourceFaultConfig(
                    type=FaultType.CPU_PRESSURE,
                    name=fault_def.get("name", "CPU Pressure"),
                    resource_type="cpu",
                    cpu_cores=fault_def.get("cores", 2),
                    cpu_percentage=fault_def.get("percentage", 80),
                    duration=fault_def.get("duration", 60)
                )
            else:
                fault = FaultConfig(
                    type=fault_type,
                    name=fault_def.get("name", "Generic Fault"),
                    duration=fault_def.get("duration", 60)
                )
            
            faults.append(fault)
        
        return ChaosExperimentConfig(
            name=scenario.get("name", "Scenario Test"),
            description=scenario.get("description"),
            faults=faults,
            dry_run=scenario.get("dry_run", False),
            parallel_execution=scenario.get("parallel", False)
        )


class MCPChaosTestSuite:
    """Pre-built chaos test suite for MCP servers."""
    
    @staticmethod
    def get_standard_tests() -> List[Dict[str, Any]]:
        """Get standard chaos test scenarios for MCP servers."""
        
        return [
            {
                "name": "Network Latency Test",
                "description": "Test MCP server with network latency",
                "faults": [
                    {
                        "type": "network_latency",
                        "latency_ms": 500,
                        "duration": 30
                    }
                ]
            },
            {
                "name": "High CPU Load Test",
                "description": "Test MCP server under CPU pressure",
                "faults": [
                    {
                        "type": "cpu_pressure",
                        "cores": 4,
                        "percentage": 90,
                        "duration": 30
                    }
                ]
            },
            {
                "name": "Memory Pressure Test",
                "description": "Test MCP server with limited memory",
                "faults": [
                    {
                        "type": "memory_pressure",
                        "memory_mb": 500,
                        "duration": 30
                    }
                ]
            },
            {
                "name": "Combined Stress Test",
                "description": "Multiple simultaneous faults",
                "parallel": True,
                "faults": [
                    {
                        "type": "network_latency",
                        "latency_ms": 200,
                        "duration": 60
                    },
                    {
                        "type": "cpu_pressure",
                        "cores": 2,
                        "percentage": 70,
                        "duration": 60
                    }
                ]
            },
            {
                "name": "Network Partition Test",
                "description": "Simulate network partition",
                "faults": [
                    {
                        "type": "network_partition",
                        "duration": 20
                    }
                ]
            },
            {
                "name": "Packet Loss Test",
                "description": "Test with packet loss",
                "faults": [
                    {
                        "type": "packet_loss",
                        "loss_percentage": 10,
                        "duration": 30
                    }
                ]
            }
        ]
    
    @staticmethod
    def get_advanced_tests() -> List[Dict[str, Any]]:
        """Get advanced chaos test scenarios."""
        
        return [
            {
                "name": "Cascading Failure Test",
                "description": "Progressive fault injection",
                "faults": [
                    {
                        "type": "network_latency",
                        "latency_ms": 100,
                        "duration": 20
                    },
                    {
                        "type": "network_latency",
                        "latency_ms": 500,
                        "duration": 20
                    },
                    {
                        "type": "network_latency",
                        "latency_ms": 2000,
                        "duration": 20
                    }
                ]
            },
            {
                "name": "Resource Exhaustion Test",
                "description": "Gradual resource exhaustion",
                "faults": [
                    {
                        "type": "memory_pressure",
                        "memory_mb": 100,
                        "duration": 30
                    },
                    {
                        "type": "memory_pressure",
                        "memory_mb": 300,
                        "duration": 30
                    },
                    {
                        "type": "memory_pressure",
                        "memory_mb": 700,
                        "duration": 30
                    }
                ]
            },
            {
                "name": "Chaos Monkey Test",
                "description": "Random fault injection",
                "randomize": True,
                "faults": [
                    {
                        "type": "network_latency",
                        "latency_ms": 1000,
                        "duration": 10,
                        "probability": 0.3
                    },
                    {
                        "type": "cpu_pressure",
                        "cores": 2,
                        "percentage": 95,
                        "duration": 10,
                        "probability": 0.3
                    },
                    {
                        "type": "packet_loss",
                        "loss_percentage": 20,
                        "duration": 10,
                        "probability": 0.3
                    }
                ]
            }
        ]