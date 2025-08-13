#!/usr/bin/env python3
"""
Test 1: Configuration Creation and Validation

This test verifies that the configuration models work correctly and can be
created, validated, and serialized without errors.
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from mcp_reliability_lab.core.config import (
        MCPServerConfig, StdioTransportConfig, MCPRetryConfig,
        MCPTimeoutConfig, MCPObservabilityConfig, 
        ServerType, TransportType
    )
    from mcp_reliability_lab.sandbox.config import (
        SandboxConfig, ModalSandboxConfig, ResourceLimits, 
        NetworkConfig, VolumeMount, SandboxProvider
    )
    from mcp_reliability_lab.chaos.config import (
        ChaosExperimentConfig, NetworkFaultConfig, ResourceFaultConfig,
        FaultType, NetworkFaultType, ResourceType, SafetyConfig
    )
    print("✓ All configuration imports successful")
except Exception as e:
    print(f"✗ Configuration import failed: {e}")
    sys.exit(1)

def test_basic_mcp_config():
    """Test basic MCP server configuration creation."""
    print("\n--- Testing Basic MCP Configuration ---")
    
    try:
        # Test StdioTransportConfig
        stdio_config = StdioTransportConfig(
            command=["python", "examples/simple_mcp_server.py"]
        )
        print(f"✓ StdioTransportConfig created: {stdio_config.type}")
        
        # Test MCPServerConfig
        server_config = MCPServerConfig(
            server_type=ServerType.PYTHON,
            transport_config=stdio_config
        )
        print(f"✓ MCPServerConfig created: {server_config.server_type}")
        
        # Test serialization
        config_dict = server_config.model_dump()
        print(f"✓ Configuration serialized: {len(config_dict)} fields")
        
        # Test with custom retry and timeout configs
        retry_config = MCPRetryConfig(max_attempts=5, initial_delay=2.0)
        timeout_config = MCPTimeoutConfig(connection_timeout=15.0)
        
        advanced_config = MCPServerConfig(
            server_type=ServerType.PYTHON,
            transport_config=StdioTransportConfig(
                command=["python", "test_server.py"],
                timeout_config=timeout_config
            ),
            retry_config=retry_config
        )
        print(f"✓ Advanced configuration created with {retry_config.max_attempts} max attempts")
        
        return True
        
    except Exception as e:
        print(f"✗ Basic MCP config test failed: {e}")
        return False

def test_sandbox_config():
    """Test sandbox configuration creation and validation."""
    print("\n--- Testing Sandbox Configuration ---")
    
    try:
        # Test basic SandboxConfig
        basic_config = SandboxConfig(
            name="test-sandbox",
            provider=SandboxProvider.MODAL
        )
        print(f"✓ Basic SandboxConfig created: {basic_config.name}")
        
        # Test ModalSandboxConfig with resources
        resources = ResourceLimits(
            cpu=4.0,
            memory=4096,
            timeout=1800
        )
        
        modal_config = ModalSandboxConfig(
            name="modal-test",
            image="python:3.11-slim",
            resources=resources,
            pip_packages=["pytest", "requests"]
        )
        print(f"✓ ModalSandboxConfig created: {modal_config.resources.cpu} CPU cores")
        
        # Test network configuration
        network = NetworkConfig(
            isolation=True,
            allowed_hosts=["httpbin.org", "api.github.com"]
        )
        
        network_config = SandboxConfig(
            name="network-test",
            network=network
        )
        print(f"✓ Network config created with {len(network.allowed_hosts)} allowed hosts")
        
        # Test volume mounts
        volume = VolumeMount(
            source="/tmp/test-data",
            target="/data",
            read_only=True
        )
        
        volume_config = SandboxConfig(
            name="volume-test",
            volumes=[volume]
        )
        print(f"✓ Volume mount config created: {volume.source} -> {volume.target}")
        
        # Test name validation
        try:
            invalid_config = SandboxConfig(
                name="Invalid Name!",  # Contains space and special char
                provider=SandboxProvider.MODAL
            )
            print("✗ Name validation should have failed")
            return False
        except ValueError:
            print("✓ Name validation correctly rejected invalid name")
        
        return True
        
    except Exception as e:
        print(f"✗ Sandbox config test failed: {e}")
        return False

def test_chaos_config():
    """Test chaos engineering configuration creation and validation."""
    print("\n--- Testing Chaos Configuration ---")
    
    try:
        # Test network fault configuration
        network_fault = NetworkFaultConfig(
            type=FaultType.NETWORK_LATENCY,
            name="latency-test",
            description="Add 100ms latency",
            network_type=NetworkFaultType.LATENCY,
            latency_ms=100,
            duration=60,
            target_hosts=["api.example.com"]
        )
        print(f"✓ NetworkFaultConfig created: {network_fault.latency_ms}ms latency")
        
        # Test resource fault configuration
        resource_fault = ResourceFaultConfig(
            type=FaultType.CPU_PRESSURE,
            name="cpu-stress",
            description="Apply CPU pressure",
            resource_type=ResourceType.CPU,
            cpu_percentage=80.0,
            duration=120
        )
        print(f"✓ ResourceFaultConfig created: {resource_fault.cpu_percentage}% CPU pressure")
        
        # Test safety configuration
        safety = SafetyConfig(
            max_error_rate=0.3,
            max_latency_ms=5000,
            health_check_interval=5
        )
        print(f"✓ SafetyConfig created: {safety.max_error_rate} max error rate")
        
        # Test complete experiment configuration
        experiment = ChaosExperimentConfig(
            name="test-experiment",
            description="Test network and CPU faults",
            faults=[network_fault, resource_fault],
            total_duration=300,
            target_services=["mcp-server"],
            safety=safety
        )
        print(f"✓ ChaosExperimentConfig created with {len(experiment.faults)} faults")
        
        # Test duration validation
        try:
            invalid_experiment = ChaosExperimentConfig(
                name="invalid-duration",
                faults=[network_fault],
                total_duration=100000  # Way too long
            )
            print("✗ Duration validation should have failed")
            return False
        except ValueError:
            print("✓ Duration validation correctly rejected excessive duration")
        
        # Test empty faults validation
        try:
            no_faults_experiment = ChaosExperimentConfig(
                name="no-faults",
                faults=[]  # Empty faults list
            )
            print("✗ Empty faults validation should have failed")
            return False
        except ValueError:
            print("✓ Empty faults validation correctly rejected empty faults list")
        
        return True
        
    except Exception as e:
        print(f"✗ Chaos config test failed: {e}")
        return False

def test_config_serialization():
    """Test that configurations can be serialized to and from JSON/dict."""
    print("\n--- Testing Configuration Serialization ---")
    
    try:
        # Create a complex configuration
        stdio_config = StdioTransportConfig(
            command=["python", "server.py"],
            working_directory="/tmp",
            environment_variables={"DEBUG": "1"}
        )
        
        server_config = MCPServerConfig(
            server_type=ServerType.PYTHON,
            transport_config=stdio_config,
            retry_config=MCPRetryConfig(max_attempts=3),
            enable_io_capture=True
        )
        
        # Serialize to dict
        config_dict = server_config.model_dump()
        print(f"✓ Serialized config to dict with {len(config_dict)} top-level keys")
        
        # Recreate from dict
        reconstructed = MCPServerConfig(**config_dict)
        print(f"✓ Reconstructed config: {reconstructed.server_type}")
        
        # Verify they're equivalent
        assert reconstructed.server_type == server_config.server_type
        assert reconstructed.transport_config.command == server_config.transport_config.command
        assert reconstructed.retry_config.max_attempts == server_config.retry_config.max_attempts
        print("✓ Original and reconstructed configs are equivalent")
        
        return True
        
    except Exception as e:
        print(f"✗ Config serialization test failed: {e}")
        return False

def main():
    """Run all configuration tests."""
    print("=== MCP Reliability Lab Configuration Tests ===")
    
    results = []
    
    # Run individual tests
    results.append(("Basic MCP Config", test_basic_mcp_config()))
    results.append(("Sandbox Config", test_sandbox_config()))
    results.append(("Chaos Config", test_chaos_config()))
    results.append(("Config Serialization", test_config_serialization()))
    
    # Print summary
    print("\n=== Test Summary ===")
    passed = 0
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("✓ All configuration components are working correctly!")
        return True
    else:
        print("✗ Some configuration components have issues")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)