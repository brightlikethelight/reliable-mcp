#!/usr/bin/env python3
"""
Modal Sandbox Orchestration Demo

This example demonstrates the comprehensive Modal sandbox capabilities
for MCP agent reliability testing.
"""

import asyncio
import json
import logging
from pathlib import Path

from mcp_reliability_lab.sandbox import (
    SandboxManager, get_sandbox_template, create_custom_template
)
from mcp_reliability_lab.observability import setup_telemetry


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def basic_modal_sandbox_demo():
    """Demonstrate basic Modal sandbox functionality."""
    print("🚀 Modal Sandbox Basic Demo")
    print("=" * 50)
    
    # Create sandbox manager
    manager = SandboxManager(
        default_provider="modal",
        max_concurrent_sandboxes=5,
        enable_metrics=True
    )
    
    async with manager:
        # Use pre-configured template
        config = get_sandbox_template("python_default")
        
        # Create and test sandbox
        async with manager.sandbox_context(config) as sandbox:
            print(f"✅ Sandbox created: {sandbox.sandbox_id}")
            
            # Test basic Python execution
            result = await sandbox.execute([
                "python", "-c", 
                "import sys; print(f'Python {sys.version_info.major}.{sys.version_info.minor}')"
            ])
            
            print(f"🐍 Python version: {result.stdout.strip()}")
            
            # Test package installation
            result = await sandbox.execute([
                "pip", "list", "|", "grep", "mcp"
            ])
            
            if result.exit_code == 0:
                print("📦 MCP package available")
            else:
                print("⚠️  MCP package not found")
            
            # Test file operations
            await sandbox.write_file("/tmp/test.txt", "Hello from Modal sandbox!")
            
            result = await sandbox.execute(["cat", "/tmp/test.txt"])
            print(f"📄 File content: {result.stdout.strip()}")
        
        print("🧹 Sandbox automatically cleaned up")


async def mcp_server_deployment_demo():
    """Demonstrate MCP server deployment in Modal sandbox."""
    print("\n🏗️  MCP Server Deployment Demo")
    print("=" * 50)
    
    manager = SandboxManager()
    
    async with manager:
        # Use template optimized for MCP servers
        config = get_sandbox_template("python_default")
        
        async with manager.sandbox_context(config) as sandbox:
            print(f"📦 Deploying MCP server in: {sandbox.sandbox_id}")
            
            # Copy our example MCP server
            server_path = str(Path(__file__).parent / "simple_mcp_server.py")
            
            try:
                server_url = await sandbox.deploy_mcp_server(
                    str(Path(__file__).parent),  # Copy entire examples directory
                    {
                        "mode": "test",
                        "tools": ["calculator", "weather"]
                    },
                    port=8000
                )
                
                print(f"🎯 MCP server deployed at: {server_url}")
                
                # Test server health (this might fail in mock mode)
                try:
                    result = await sandbox.execute([
                        "curl", "-s", f"{server_url}/health"
                    ])
                    
                    if result.exit_code == 0:
                        print("✅ Server health check passed")
                    else:
                        print("ℹ️  Server health check not available (expected in demo)")
                
                except Exception as e:
                    print(f"ℹ️  Health check error (expected): {e}")
                
            except Exception as e:
                print(f"ℹ️  Deployment simulation (Modal not fully configured): {e}")


async def parallel_testing_demo():
    """Demonstrate parallel testing across multiple sandboxes."""
    print("\n⚡ Parallel Testing Demo")  
    print("=" * 50)
    
    manager = SandboxManager()
    
    async with manager:
        # Create multiple test scenarios
        test_configs = [
            ("python_minimal", ["echo", "Test 1"]),
            ("python_default", ["python", "-c", "print('Test 2: Python works')"]),
            ("minimal", ["sh", "-c", "echo 'Test 3: Shell works'"]),
        ]
        
        print(f"🎯 Running {len(test_configs)} tests in parallel...")
        
        async def run_test(template_name, command):
            """Run a single test in a sandbox."""
            config = get_sandbox_template(template_name)
            config.name = f"{template_name}-test"
            
            async with manager.sandbox_context(config) as sandbox:
                result = await sandbox.execute(command, timeout=30)
                return {
                    "template": template_name,
                    "command": " ".join(command),
                    "status": result.status,
                    "output": result.stdout.strip(),
                    "sandbox_id": sandbox.sandbox_id
                }
        
        # Run tests concurrently
        tasks = [run_test(template, cmd) for template, cmd in test_configs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Display results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"❌ Test {i+1} failed: {result}")
            else:
                print(f"✅ Test {i+1} ({result['template']}): {result['output']}")


async def experiment_orchestration_demo():
    """Demonstrate full experiment orchestration."""
    print("\n🔬 Experiment Orchestration Demo")
    print("=" * 50)
    
    manager = SandboxManager(enable_metrics=True)
    
    # Define experiment configuration
    experiment_config = {
        "name": "mcp_reliability_experiment",
        "sandboxes": [
            get_sandbox_template("python_default").model_dump(),
            get_sandbox_template("python_minimal").model_dump()
        ],
        "servers": [
            {
                "name": "test_server_1",
                "path": str(Path(__file__).parent),
                "config": {"mode": "test", "port": 8000}
            }
        ],
        "test_suites": [
            {
                "name": "basic_functionality",
                "path": str(Path(__file__).parent.parent / "tests" / "unit"),
                "config": {"verbose": True}
            }
        ]
    }
    
    async with manager:
        print("🚀 Starting experiment orchestration...")
        
        try:
            results = await manager.orchestrate_experiment(experiment_config)
            
            print(f"📊 Experiment Results:")
            print(f"   - ID: {results['experiment_id']}")
            print(f"   - Status: {results['status']}")
            print(f"   - Duration: {results.get('duration', 0):.2f}s")
            print(f"   - Sandboxes: {len(results['sandboxes'])}")
            print(f"   - Test Results: {len(results['results'])}")
            
            # Show individual results
            for i, test_result in enumerate(results.get('results', [])[:3]):  # Show first 3
                print(f"   Test {i+1}: {test_result['test_suite']} -> {test_result['result']['status']}")
                
        except Exception as e:
            print(f"ℹ️  Experiment simulation (Modal not configured): {e}")


async def custom_template_demo():
    """Demonstrate custom template creation."""
    print("\n🎨 Custom Template Demo")
    print("=" * 50)
    
    # Create custom template for MCP testing
    custom_template = create_custom_template(
        name="mcp-chaos-testing",
        base_template="python_default",
        resources={
            "cpu": 4.0,
            "memory": 4096,
            "timeout": 1800
        },
        pip_packages=[
            "mcp>=0.1.0",
            "chaos-toolkit>=1.18.0",
            "locust>=2.20.0",
            "hypothesis>=6.100.0"
        ]
    )
    
    print(f"🛠️  Created custom template: {custom_template.name}")
    print(f"   - CPU: {custom_template.resources.cpu} cores")
    print(f"   - Memory: {custom_template.resources.memory} MB")
    print(f"   - Packages: {len(custom_template.pip_packages)} pip packages")
    
    manager = SandboxManager()
    
    async with manager:
        async with manager.sandbox_context(custom_template) as sandbox:
            print(f"✅ Custom sandbox created: {sandbox.sandbox_id}")
            
            # Test that chaos toolkit is available
            result = await sandbox.execute([
                "python", "-c", "import chaos; print('Chaos Toolkit available')"
            ])
            
            if result.exit_code == 0:
                print("🌪️  Chaos Toolkit ready for testing")
            else:
                print("ℹ️  Chaos Toolkit not available (expected in simulation)")


async def resource_monitoring_demo():
    """Demonstrate resource monitoring and metrics."""
    print("\n📊 Resource Monitoring Demo")
    print("=" * 50)
    
    # Setup telemetry
    setup_telemetry(service_name="modal-sandbox-demo")
    
    manager = SandboxManager(enable_metrics=True)
    
    async with manager:
        # Create sandbox with resource limits
        config = get_sandbox_template("minimal")
        sandbox = await manager.create_sandbox(config)
        
        print(f"📈 Monitoring sandbox: {sandbox.sandbox_id}")
        
        # Get initial metrics
        metrics = manager.get_sandbox_metrics(sandbox.sandbox_id)
        print(f"   - Provider: {metrics['provider']}")
        print(f"   - Status: {metrics['status']}")
        print(f"   - Uptime: {metrics['uptime']:.2f}s")
        
        # Run some commands and monitor
        commands = [
            ["echo", "Memory test"],
            ["python", "-c", "import sys; print(f'Platform: {sys.platform}')"],
            ["ls", "-la", "/tmp"]
        ]
        
        for i, command in enumerate(commands):
            print(f"   Running command {i+1}: {' '.join(command)}")
            result = await manager.execute_in_sandbox(
                sandbox.sandbox_id,
                command
            )
            print(f"   Result: {result.status}")
        
        # Get final metrics
        final_metrics = manager.get_sandbox_metrics(sandbox.sandbox_id)
        print(f"📊 Final uptime: {final_metrics['uptime']:.2f}s")
        
        # Get active sandboxes list
        active = manager.get_active_sandboxes()
        print(f"🔧 Active sandboxes: {len(active)}")
        
        # Cleanup
        await manager.destroy_sandbox(sandbox.sandbox_id)


async def main():
    """Run all Modal sandbox demos."""
    print("🌟 MCP Agent Reliability Lab - Modal Sandbox Demos")
    print("=" * 60)
    
    try:
        await basic_modal_sandbox_demo()
        await mcp_server_deployment_demo()
        await parallel_testing_demo()
        await experiment_orchestration_demo()
        await custom_template_demo()
        await resource_monitoring_demo()
        
        print("\n🎉 All Modal sandbox demos completed!")
        print("\nKey Features Demonstrated:")
        print("✅ Dynamic container creation with Modal")
        print("✅ MCP server deployment and orchestration") 
        print("✅ Parallel test execution across sandboxes")
        print("✅ Full experiment orchestration")
        print("✅ Custom template creation")
        print("✅ Resource monitoring and metrics")
        print("✅ Automatic cleanup and lifecycle management")
        
        print("\nNext Steps:")
        print("- Configure Modal CLI: pip install modal && modal setup")
        print("- Set up Modal secrets for production use")
        print("- Explore chaos engineering features")
        print("- Scale testing to 100+ concurrent sandboxes")
        
    except Exception as e:
        print(f"\n💡 Demo running in simulation mode")
        print(f"Install and configure Modal to see full functionality: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())