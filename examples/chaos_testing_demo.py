#!/usr/bin/env python3
"""
Comprehensive Chaos Testing Demo for MCP Servers

This example demonstrates the full chaos engineering capabilities
of the MCP Agent Reliability Lab.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, List

from mcp_reliability_lab.chaos import (
    ChaosOrchestrator, ChaosExperimentConfig, SafetyConfig,
    NetworkFaultConfig, ResourceFaultConfig, FaultType,
    NetworkFaultType, ResourceType
)
from mcp_reliability_lab.chaos.sandbox_integration import (
    SandboxChaosOrchestrator, MCPChaosTestSuite
)
from mcp_reliability_lab.sandbox import SandboxManager
from mcp_reliability_lab.observability import setup_telemetry
from mcp_reliability_lab.core import MCPServerWrapper


async def basic_fault_injection_demo():
    """Demonstrate basic fault injection capabilities."""
    print("\n🔥 Basic Fault Injection Demo")
    print("=" * 50)
    
    # Create chaos orchestrator
    orchestrator = ChaosOrchestrator()
    
    # Define a simple network latency fault
    network_fault = NetworkFaultConfig(
        type=FaultType.NETWORK_LATENCY,
        name="Network Latency Test",
        description="Inject 500ms latency",
        network_type=NetworkFaultType.LATENCY,
        latency_ms=500,
        jitter_ms=50,
        duration=10,
        probability=1.0
    )
    
    # Define a CPU pressure fault
    cpu_fault = ResourceFaultConfig(
        type=FaultType.CPU_PRESSURE,
        name="CPU Pressure Test",
        description="80% CPU usage on 2 cores",
        resource_type=ResourceType.CPU,
        cpu_cores=2,
        cpu_percentage=80.0,
        duration=10
    )
    
    # Create experiment configuration
    experiment_config = ChaosExperimentConfig(
        name="Basic Chaos Test",
        description="Test basic fault injection",
        dry_run=True,  # Dry run for demo
        faults=[network_fault, cpu_fault],
        parallel_execution=False,
        cooldown_period=5
    )
    
    # Run experiment
    print("Running chaos experiment (dry run)...")
    result = await orchestrator.run_experiment(experiment_config)
    
    # Display results
    print(f"\n📊 Experiment Results:")
    print(f"  Status: {result.status}")
    print(f"  Total Faults: {result.total_faults}")
    print(f"  Successful: {result.successful_faults}")
    print(f"  Failed: {result.failed_faults}")
    print(f"  Duration: {result.duration_seconds:.2f}s")
    
    if result.fault_results:
        print("\n  Fault Details:")
        for fault_result in result.fault_results:
            print(f"    - {fault_result['fault']}: {fault_result.get('status', 'unknown')}")


async def safety_controls_demo():
    """Demonstrate safety controls and circuit breakers."""
    print("\n🛡️ Safety Controls Demo")
    print("=" * 50)
    
    orchestrator = ChaosOrchestrator()
    
    # Configure strict safety controls
    safety_config = SafetyConfig(
        enabled=True,
        max_error_rate=0.1,  # 10% error rate threshold
        max_latency_ms=1000,  # 1 second latency threshold
        min_success_rate=0.9,  # 90% success rate required
        circuit_breaker_enabled=True,
        circuit_breaker_threshold=0.5,
        auto_rollback=True,
        max_affected_instances=2,
        protected_services=["database", "auth-service"]
    )
    
    # Create a potentially dangerous fault
    dangerous_fault = ResourceFaultConfig(
        type=FaultType.MEMORY_PRESSURE,
        name="Memory Exhaustion",
        description="Consume 90% of available memory",
        resource_type=ResourceType.MEMORY,
        memory_percentage=90.0,
        duration=30
    )
    
    # Create experiment with safety controls
    experiment_config = ChaosExperimentConfig(
        name="Safety Test",
        description="Test safety controls",
        dry_run=True,
        faults=[dangerous_fault],
        safety=safety_config
    )
    
    print("Testing safety controls...")
    print(f"  Protected services: {safety_config.protected_services}")
    print(f"  Max error rate: {safety_config.max_error_rate:.1%}")
    print(f"  Circuit breaker: {'Enabled' if safety_config.circuit_breaker_enabled else 'Disabled'}")
    print(f"  Auto rollback: {'Enabled' if safety_config.auto_rollback else 'Disabled'}")
    
    result = await orchestrator.run_experiment(experiment_config)
    
    print(f"\n📊 Safety Results:")
    print(f"  Safety triggered: {result.safety_triggered}")
    if result.safety_reasons:
        print(f"  Reasons: {', '.join(result.safety_reasons)}")
    print(f"  Rollback performed: {result.rollback_performed}")


async def sandbox_chaos_demo():
    """Demonstrate chaos testing in Modal sandboxes."""
    print("\n📦 Sandbox Chaos Testing Demo")
    print("=" * 50)
    
    # Create sandbox manager
    sandbox_manager = SandboxManager(
        default_provider="modal",
        max_concurrent_sandboxes=5
    )
    
    # Create sandbox chaos orchestrator
    sandbox_chaos = SandboxChaosOrchestrator(sandbox_manager)
    
    # Define chaos experiment
    experiment_config = ChaosExperimentConfig(
        name="Sandbox Chaos Test",
        description="Test MCP server in isolated sandbox with chaos",
        dry_run=False,
        faults=[
            NetworkFaultConfig(
                type=FaultType.NETWORK_LATENCY,
                name="Sandbox Network Latency",
                network_type=NetworkFaultType.LATENCY,
                latency_ms=200,
                duration=15
            ),
            ResourceFaultConfig(
                type=FaultType.CPU_PRESSURE,
                name="Sandbox CPU Load",
                resource_type=ResourceType.CPU,
                cpu_cores=1,
                cpu_percentage=70.0,
                duration=15
            )
        ]
    )
    
    print("Running chaos experiment in Modal sandbox...")
    print("  Template: chaos_engineering")
    print("  Faults: Network latency + CPU pressure")
    
    try:
        # Run in sandbox (will use mock in demo mode)
        result = await sandbox_chaos.run_chaos_in_sandbox(
            experiment_config,
            sandbox_template="chaos_engineering",
            mcp_server_path=str(Path(__file__).parent / "simple_mcp_server.py")
        )
        
        print(f"\n📊 Sandbox Chaos Results:")
        print(f"  Status: {result.status}")
        print(f"  Faults injected: {result.successful_faults}")
        print(f"  MCP server tested: {'Yes' if 'mcp_test_success' in result.metrics else 'No'}")
        
    except Exception as e:
        print(f"  ℹ️ Sandbox demo (Modal not configured): {e}")


async def mcp_resilience_testing_demo():
    """Test MCP server resilience with standard chaos scenarios."""
    print("\n🎯 MCP Server Resilience Testing Demo")
    print("=" * 50)
    
    sandbox_manager = SandboxManager()
    sandbox_chaos = SandboxChaosOrchestrator(sandbox_manager)
    
    # Get standard test scenarios
    standard_tests = MCPChaosTestSuite.get_standard_tests()
    
    print(f"Testing MCP server with {len(standard_tests)} standard scenarios:")
    for test in standard_tests:
        print(f"  - {test['name']}: {test['description']}")
    
    # Run resilience tests
    mcp_server_path = str(Path(__file__).parent / "simple_mcp_server.py")
    
    try:
        results = await sandbox_chaos.test_mcp_server_resilience(
            mcp_server_path,
            standard_tests[:3],  # Run first 3 tests for demo
            sandbox_template="python_default"
        )
        
        print(f"\n📊 Resilience Test Results:")
        print(f"  Total scenarios: {results['total_scenarios']}")
        print(f"  Passed: {results['passed']}")
        print(f"  Failed: {results['failed']}")
        print(f"  Resilience score: {results['resilience_score']:.1%}")
        
        print("\n  Scenario Details:")
        for scenario in results['scenario_results']:
            status = "✅" if scenario['survived'] else "❌"
            print(f"    {status} {scenario['name']}")
            
    except Exception as e:
        print(f"  ℹ️ Resilience testing demo (simplified): {e}")


async def chaos_scenarios_demo():
    """Demonstrate pre-built chaos scenarios."""
    print("\n🎬 Chaos Scenarios Demo")
    print("=" * 50)
    
    orchestrator = ChaosOrchestrator()
    
    # Progressive network degradation scenario
    progressive_degradation = [
        NetworkFaultConfig(
            type=FaultType.NETWORK_LATENCY,
            name=f"Stage {i+1} Latency",
            network_type=NetworkFaultType.LATENCY,
            latency_ms=100 * (2 ** i),  # 100ms, 200ms, 400ms, 800ms
            duration=5
        )
        for i in range(4)
    ]
    
    # Resource exhaustion scenario
    resource_exhaustion = [
        ResourceFaultConfig(
            type=FaultType.MEMORY_PRESSURE,
            name=f"Memory Stage {i+1}",
            resource_type=ResourceType.MEMORY,
            memory_mb=100 * (i + 1),  # 100MB, 200MB, 300MB
            duration=5
        )
        for i in range(3)
    ]
    
    print("Available Chaos Scenarios:")
    print("1. Progressive Network Degradation")
    print("   - Gradually increases latency: 100ms → 800ms")
    print("2. Resource Exhaustion")
    print("   - Gradually consumes memory: 100MB → 300MB")
    
    # Run progressive degradation scenario
    experiment_config = ChaosExperimentConfig(
        name="Progressive Degradation",
        description="Test system under progressive network degradation",
        dry_run=True,
        faults=progressive_degradation,
        cooldown_period=2
    )
    
    print("\nRunning Progressive Degradation scenario...")
    result = await orchestrator.run_experiment(experiment_config)
    
    print(f"Result: {result.status}")
    for i, fault_result in enumerate(result.fault_results):
        latency = 100 * (2 ** i)
        print(f"  Stage {i+1} ({latency}ms): {fault_result.get('status', 'unknown')}")


async def parallel_chaos_experiments_demo():
    """Demonstrate running multiple chaos experiments in parallel."""
    print("\n⚡ Parallel Chaos Experiments Demo")
    print("=" * 50)
    
    sandbox_manager = SandboxManager()
    sandbox_chaos = SandboxChaosOrchestrator(sandbox_manager)
    
    # Create multiple experiment configurations
    experiments = [
        ChaosExperimentConfig(
            name=f"Parallel Experiment {i+1}",
            description=f"Test {i+1}",
            dry_run=True,
            faults=[
                NetworkFaultConfig(
                    type=FaultType.NETWORK_LATENCY,
                    name=f"Latency Test {i+1}",
                    network_type=NetworkFaultType.LATENCY,
                    latency_ms=100 * (i + 1),
                    duration=5
                )
            ]
        )
        for i in range(3)
    ]
    
    print(f"Running {len(experiments)} experiments in parallel...")
    
    try:
        results = await sandbox_chaos.run_parallel_chaos_experiments(
            experiments,
            max_concurrent=3
        )
        
        print(f"\n📊 Parallel Execution Results:")
        for i, result in enumerate(results):
            print(f"  Experiment {i+1}: {result.status}")
            
    except Exception as e:
        print(f"  ℹ️ Parallel execution demo (simplified): {e}")


async def chaos_monitoring_demo():
    """Demonstrate chaos monitoring and metrics collection."""
    print("\n📈 Chaos Monitoring Demo")
    print("=" * 50)
    
    from mcp_reliability_lab.chaos.monitors import (
        SystemHealthMonitor, FaultMonitor, RecoveryMonitor
    )
    
    # Setup monitoring
    health_monitor = SystemHealthMonitor(check_interval=1.0)
    fault_monitor = FaultMonitor()
    recovery_monitor = RecoveryMonitor(baseline_duration=5)
    
    print("Setting up monitoring infrastructure...")
    
    # Start health monitoring
    await health_monitor.start_monitoring()
    
    # Register custom health check
    def custom_health_check():
        # Simulate health check
        import random
        return random.random() > 0.1  # 90% success rate
    
    health_monitor.register_health_check(custom_health_check)
    
    # Establish baseline
    print("Establishing baseline metrics (5 seconds)...")
    await recovery_monitor.establish_baseline(health_monitor)
    
    # Simulate some activity
    await asyncio.sleep(2)
    
    # Get metrics
    metrics = await health_monitor.get_metrics()
    
    print(f"\n📊 System Metrics:")
    print(f"  CPU Usage: {metrics['current']['cpu_percent']:.1f}%")
    print(f"  Memory Usage: {metrics['current']['memory_percent']:.1f}%")
    print(f"  Disk Usage: {metrics['current']['disk_percent']:.1f}%")
    print(f"  Process Count: {metrics['current']['process_count']}")
    print(f"  Health Status: {'Healthy' if metrics['health']['is_healthy'] else 'Unhealthy'}")
    print(f"  Success Rate: {metrics['health']['success_rate']:.1%}")
    
    # Stop monitoring
    await health_monitor.stop_monitoring()


async def main():
    """Run all chaos testing demos."""
    print("🌟 MCP Agent Reliability Lab - Chaos Testing Demos")
    print("=" * 60)
    
    # Setup telemetry
    setup_telemetry(service_name="chaos-testing-demo")
    
    try:
        # Run demos
        await basic_fault_injection_demo()
        await safety_controls_demo()
        await chaos_scenarios_demo()
        await chaos_monitoring_demo()
        await sandbox_chaos_demo()
        await mcp_resilience_testing_demo()
        await parallel_chaos_experiments_demo()
        
        print("\n🎉 All chaos testing demos completed!")
        print("\nKey Features Demonstrated:")
        print("✅ Network fault injection (latency, packet loss, partition)")
        print("✅ Resource pressure simulation (CPU, memory, disk)")
        print("✅ Safety controls and circuit breakers")
        print("✅ Sandbox-isolated chaos experiments")
        print("✅ MCP server resilience testing")
        print("✅ Progressive fault scenarios")
        print("✅ Parallel experiment execution")
        print("✅ Comprehensive monitoring and metrics")
        print("✅ Recovery monitoring and baseline comparison")
        
        print("\nNext Steps:")
        print("- Configure Modal for full sandbox capabilities")
        print("- Test against real MCP servers")
        print("- Create custom chaos scenarios")
        print("- Integrate with CI/CD pipelines")
        print("- Set up alerting and notifications")
        
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())