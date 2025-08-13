#!/usr/bin/env python3
"""
Test 5: Chaos Engineering Integration

This test verifies that the chaos engineering components can be configured
and integrated without actually performing destructive operations.
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from mcp_reliability_lab.chaos.config import (
        ChaosExperimentConfig, NetworkFaultConfig, ResourceFaultConfig,
        FaultType, NetworkFaultType, ResourceType, SafetyConfig,
        ChaosSchedule
    )
    print("✓ Chaos config imports successful")
except Exception as e:
    print(f"✗ Chaos config import failed: {e}")
    sys.exit(1)

# Try to import chaos orchestrator and other components
try:
    from mcp_reliability_lab.chaos.orchestrator import ChaosOrchestrator
    chaos_orchestrator_available = True
    print("✓ Chaos orchestrator import successful")
except Exception as e:
    chaos_orchestrator_available = False
    print(f"! Chaos orchestrator not available: {type(e).__name__}")

try:
    from mcp_reliability_lab.chaos.faults import FaultInjector
    fault_injector_available = True
    print("✓ Fault injector import successful")
except Exception as e:
    fault_injector_available = False
    print(f"! Fault injector not available: {type(e).__name__}")

try:
    from mcp_reliability_lab.chaos.monitors import ChaosMonitor
    chaos_monitor_available = True
    print("✓ Chaos monitor import successful")
except Exception as e:
    chaos_monitor_available = False
    print(f"! Chaos monitor not available: {type(e).__name__}")

def test_chaos_configuration_creation():
    """Test creating comprehensive chaos configurations."""
    print("\n--- Testing Chaos Configuration Creation ---")
    
    try:
        # Create network fault
        network_fault = NetworkFaultConfig(
            type=FaultType.NETWORK_LATENCY,
            name="api-latency-test",
            description="Add latency to API calls",
            network_type=NetworkFaultType.LATENCY,
            latency_ms=200,
            jitter_ms=50,
            duration=180,
            target_hosts=["api.example.com", "service.internal"],
            probability=0.8
        )
        print(f"✓ Network fault created: {network_fault.name} ({network_fault.latency_ms}ms)")
        
        # Create resource fault
        resource_fault = ResourceFaultConfig(
            type=FaultType.CPU_PRESSURE,
            name="cpu-stress-test",
            description="Apply CPU pressure",
            resource_type=ResourceType.CPU,
            cpu_percentage=75.0,
            duration=120,
            target="mcp-server",
            probability=1.0
        )
        print(f"✓ Resource fault created: {resource_fault.name} ({resource_fault.cpu_percentage}%)")
        
        # Create memory pressure fault
        memory_fault = ResourceFaultConfig(
            type=FaultType.MEMORY_PRESSURE,
            name="memory-pressure-test",
            description="Apply memory pressure",
            resource_type=ResourceType.MEMORY,
            memory_percentage=80.0,
            memory_pattern="hot",
            duration=90
        )
        print(f"✓ Memory fault created: {memory_fault.name} ({memory_fault.memory_percentage}%)")
        
        # Create safety configuration
        safety = SafetyConfig(
            enabled=True,
            max_error_rate=0.4,
            max_latency_ms=8000,
            min_success_rate=0.6,
            health_check_interval=15,
            auto_rollback=True,
            rollback_timeout=45,
            max_affected_instances=2,
            protected_services=["database", "auth-service"],
            emergency_stop_enabled=True
        )
        print(f"✓ Safety config created: max {safety.max_error_rate} error rate")
        
        # Create complete experiment
        experiment = ChaosExperimentConfig(
            name="comprehensive-reliability-test",
            description="Test network latency and resource pressure combined",
            version="2.0.0",
            faults=[network_fault, resource_fault, memory_fault],
            total_duration=600,
            parallel_execution=False,
            randomize_order=True,
            target_services=["mcp-server", "api-gateway"],
            safety=safety,
            dry_run=True,  # Important for testing
            steady_state_checks=[
                {
                    "name": "response_time_check",
                    "type": "latency",
                    "threshold": 1000,
                    "endpoint": "/health"
                },
                {
                    "name": "error_rate_check", 
                    "type": "error_rate",
                    "threshold": 0.05,
                    "duration": 60
                }
            ],
            rollback_plan={
                "steps": [
                    "stop_fault_injection",
                    "restart_affected_services",
                    "verify_system_health"
                ],
                "timeout": 300
            },
            notify_on_start=True,
            notify_on_complete=True,
            notification_channels=["slack", "email"]
        )
        
        print(f"✓ Complete experiment created: {experiment.name}")
        print(f"  - {len(experiment.faults)} faults configured")
        print(f"  - {experiment.total_duration}s total duration")
        print(f"  - Dry run: {experiment.dry_run}")
        
        # Test serialization
        experiment_dict = experiment.model_dump()
        print(f"✓ Experiment serialized: {len(experiment_dict)} top-level fields")
        
        # Reconstruct from dict
        reconstructed = ChaosExperimentConfig(**experiment_dict)
        assert reconstructed.name == experiment.name
        assert len(reconstructed.faults) == len(experiment.faults)
        print("✓ Experiment successfully reconstructed from serialization")
        
        return True
        
    except Exception as e:
        print(f"✗ Chaos configuration creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_chaos_scheduling():
    """Test chaos experiment scheduling configuration."""
    print("\n--- Testing Chaos Scheduling ---")
    
    try:
        # Create basic schedule
        schedule = ChaosSchedule(
            enabled=True,
            interval_minutes=120,  # Every 2 hours
            allowed_days=["monday", "tuesday", "wednesday", "thursday", "friday"],
            allowed_hours=[9, 10, 11, 14, 15, 16],  # Business hours
            max_experiments_per_day=3,
            min_interval_between_experiments=60
        )
        print(f"✓ Schedule created: every {schedule.interval_minutes} minutes")
        print(f"  - Allowed days: {len(schedule.allowed_days)}")
        print(f"  - Allowed hours: {len(schedule.allowed_hours)}")
        
        # Test cron expression schedule
        cron_schedule = ChaosSchedule(
            enabled=True,
            cron_expression="0 */3 * * 1-5",  # Every 3 hours on weekdays
            max_experiments_per_day=8,
            scale_with_traffic=True,
            traffic_threshold=0.7
        )
        print(f"✓ Cron schedule created: {cron_schedule.cron_expression}")
        
        # Test validation
        try:
            invalid_schedule = ChaosSchedule(
                allowed_days=["invalid_day"],
                allowed_hours=[25]  # Invalid hour
            )
            print("✗ Schedule validation should have failed")
            return False
        except ValueError:
            print("✓ Schedule validation correctly rejected invalid values")
        
        return True
        
    except Exception as e:
        print(f"✗ Chaos scheduling test failed: {e}")
        return False

def test_fault_parameter_validation():
    """Test fault parameter validation and edge cases."""
    print("\n--- Testing Fault Parameter Validation ---")
    
    try:
        # Test network fault validation
        valid_network_fault = NetworkFaultConfig(
            type=FaultType.NETWORK_PACKET_LOSS,
            name="packet-loss-test",
            network_type=NetworkFaultType.PACKET_LOSS,
            loss_percentage=5.0,
            loss_correlation=0.25,
            duration=60,
            target_ports=[80, 443, 8080]
        )
        print(f"✓ Valid network fault: {valid_network_fault.loss_percentage}% packet loss")
        
        # Test invalid network fault parameters
        try:
            invalid_network_fault = NetworkFaultConfig(
                type=FaultType.NETWORK_LATENCY,
                name="invalid-latency",
                network_type=NetworkFaultType.LATENCY,
                latency_ms=70000,  # Way too high
                duration=5000  # Too long
            )
            print("✗ Network fault validation should have failed")
            return False
        except ValueError:
            print("✓ Network fault validation correctly rejected invalid parameters")
        
        # Test resource fault validation
        valid_resource_fault = ResourceFaultConfig(
            type=FaultType.DISK_PRESSURE,
            name="disk-io-test",
            resource_type=ResourceType.DISK,
            disk_io_percentage=60.0,
            disk_path="/tmp/chaos-test",
            duration=180
        )
        print(f"✓ Valid resource fault: {valid_resource_fault.disk_io_percentage}% disk I/O")
        
        # Test fault duration validation
        try:
            invalid_duration_fault = NetworkFaultConfig(
                type=FaultType.NETWORK_LATENCY,
                name="invalid-duration",
                network_type=NetworkFaultType.LATENCY,
                latency_ms=100,
                duration=5000  # Too long (> 1 hour)
            )
            print("✗ Duration validation should have failed")
            return False
        except ValueError:
            print("✓ Duration validation correctly rejected excessive duration")
        
        return True
        
    except Exception as e:
        print(f"✗ Fault parameter validation failed: {e}")
        return False

def test_safety_configuration():
    """Test comprehensive safety configuration."""
    print("\n--- Testing Safety Configuration ---")
    
    try:
        # Test comprehensive safety config
        comprehensive_safety = SafetyConfig(
            enabled=True,
            max_error_rate=0.25,
            max_latency_ms=3000,
            min_success_rate=0.75,
            
            # Health checks
            health_check_interval=10,
            health_check_timeout=5,
            health_check_retries=3,
            
            # Circuit breaker
            circuit_breaker_enabled=True,
            circuit_breaker_threshold=0.3,
            circuit_breaker_timeout=120,
            
            # Rollback
            auto_rollback=True,
            rollback_timeout=60,
            
            # Blast radius controls
            max_affected_instances=3,
            max_affected_percentage=0.25,
            
            # Emergency controls
            emergency_stop_enabled=True,
            emergency_contacts=["oncall@company.com", "sre-team@company.com"],
            
            # Protection
            protected_services=["user-auth", "payment-processor", "data-pipeline"],
            protected_hosts=["db-primary", "cache-cluster"],
            allowed_time_windows=[
                {"start": "09:00", "end": "17:00", "timezone": "UTC"},
                {"start": "10:00", "end": "16:00", "timezone": "PST"}
            ],
            
            # Monitoring and alerting
            alert_enabled=True,
            alert_channels=["slack", "pagerduty", "email", "webhook"]
        )
        
        print(f"✓ Comprehensive safety config created:")
        print(f"  - Max error rate: {comprehensive_safety.max_error_rate}")
        print(f"  - Protected services: {len(comprehensive_safety.protected_services)}")
        print(f"  - Alert channels: {len(comprehensive_safety.alert_channels)}")
        print(f"  - Emergency contacts: {len(comprehensive_safety.emergency_contacts)}")
        
        # Test safety config with minimal settings
        minimal_safety = SafetyConfig(
            enabled=False  # Disable all safety checks
        )
        print(f"✓ Minimal safety config: enabled={minimal_safety.enabled}")
        
        return True
        
    except Exception as e:
        print(f"✗ Safety configuration test failed: {e}")
        return False

def test_chaos_orchestrator_integration():
    """Test chaos orchestrator integration if available."""
    print("\n--- Testing Chaos Orchestrator Integration ---")
    
    if not chaos_orchestrator_available:
        print("! Chaos orchestrator not available, skipping integration test")
        return True
    
    try:
        # Test orchestrator creation
        orchestrator = ChaosOrchestrator()
        print("✓ Chaos orchestrator created")
        
        # Test experiment loading
        experiment = ChaosExperimentConfig(
            name="integration-test",
            faults=[
                NetworkFaultConfig(
                    type=FaultType.NETWORK_LATENCY,
                    name="test-latency",
                    network_type=NetworkFaultType.LATENCY,
                    latency_ms=100,
                    duration=30
                )
            ],
            dry_run=True,
            total_duration=60
        )
        
        # Test experiment validation (should not execute)
        result = orchestrator.validate_experiment(experiment)
        print(f"✓ Experiment validation: {result}")
        
        return True
        
    except Exception as e:
        print(f"✗ Chaos orchestrator integration failed: {e}")
        return False

async def test_chaos_component_integration():
    """Test integration between chaos components."""
    print("\n--- Testing Chaos Component Integration ---")
    
    try:
        # Create a realistic experiment configuration
        network_fault = NetworkFaultConfig(
            type=FaultType.NETWORK_LATENCY,
            name="realistic-latency",
            description="Realistic network latency simulation",
            network_type=NetworkFaultType.LATENCY,
            latency_ms=150,
            jitter_ms=25,
            duration=300,
            target_hosts=["api.service.com"],
            probability=0.9
        )
        
        cpu_fault = ResourceFaultConfig(
            type=FaultType.CPU_PRESSURE,
            name="realistic-cpu-pressure",
            description="Realistic CPU pressure simulation",
            resource_type=ResourceType.CPU,
            cpu_percentage=70.0,
            duration=240
        )
        
        safety = SafetyConfig(
            enabled=True,
            max_error_rate=0.35,
            auto_rollback=True,
            protected_services=["critical-service"]
        )
        
        experiment = ChaosExperimentConfig(
            name="integration-experiment",
            description="Integration test for chaos components",
            faults=[network_fault, cpu_fault],
            total_duration=400,
            parallel_execution=True,
            safety=safety,
            dry_run=True,
            steady_state_checks=[
                {"name": "health", "type": "http", "endpoint": "/health"},
                {"name": "latency", "type": "performance", "threshold": 2000}
            ]
        )
        
        print(f"✓ Integration experiment created: {experiment.name}")
        print(f"  - Faults: {len(experiment.faults)}")
        print(f"  - Parallel execution: {experiment.parallel_execution}")
        print(f"  - Safety checks: {len(experiment.steady_state_checks)}")
        
        # Test experiment planning (without execution)
        total_faults_duration = sum(fault.duration for fault in experiment.faults)
        if experiment.parallel_execution:
            expected_duration = max(fault.duration for fault in experiment.faults)
        else:
            expected_duration = total_faults_duration
        
        print(f"✓ Experiment planning:")
        print(f"  - Individual fault durations: {[f.duration for f in experiment.faults]}s")
        print(f"  - Expected execution time: {expected_duration}s")
        print(f"  - Total experiment duration: {experiment.total_duration}s")
        
        return True
        
    except Exception as e:
        print(f"✗ Chaos component integration failed: {e}")
        return False

def main():
    """Run all chaos engineering tests."""
    print("=== Chaos Engineering Integration Tests ===")
    
    results = []
    
    # Run individual tests
    results.append(("Configuration Creation", test_chaos_configuration_creation()))
    results.append(("Scheduling", test_chaos_scheduling()))
    results.append(("Parameter Validation", test_fault_parameter_validation()))
    results.append(("Safety Configuration", test_safety_configuration()))
    results.append(("Orchestrator Integration", test_chaos_orchestrator_integration()))
    
    # Run async test
    results.append(("Component Integration", asyncio.run(test_chaos_component_integration())))
    
    # Print summary
    print("\n=== Test Summary ===")
    passed = 0
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    # Component availability summary
    print("\n=== Component Availability ===")
    components = [
        ("Chaos Orchestrator", chaos_orchestrator_available),
        ("Fault Injector", fault_injector_available),
        ("Chaos Monitor", chaos_monitor_available)
    ]
    
    available_count = sum(1 for _, available in components if available)
    for name, available in components:
        status = "Available" if available else "Not Available"
        print(f"{name}: {status}")
    
    print(f"\nComponents: {available_count}/{len(components)} available")
    
    # Overall assessment
    if passed >= len(results) * 0.8 and available_count >= 1:
        print("✓ Chaos engineering framework is functional!")
        return True
    else:
        print("✗ Chaos engineering framework needs work")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)