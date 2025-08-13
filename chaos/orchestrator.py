"""Chaos experiment orchestration with safety controls."""

import asyncio
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
from enum import Enum
import logging
from dataclasses import dataclass, field

from opentelemetry import trace, metrics
from opentelemetry.trace import Status, StatusCode

from .config import (
    ChaosExperimentConfig, SafetyConfig, FaultConfig,
    NetworkFaultConfig, ResourceFaultConfig, ExperimentStatus
)
from .faults import (
    FaultInjector, NetworkFaultInjector, ResourceFaultInjector,
    SystemFaultInjector, TimeFaultInjector
)
from .monitors import SystemHealthMonitor, FaultMonitor


logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Metrics
experiment_counter = meter.create_counter(
    "chaos.experiments",
    description="Number of chaos experiments"
)
experiment_duration = meter.create_histogram(
    "chaos.experiment_duration",
    description="Duration of chaos experiments",
    unit="s"
)
safety_trigger_counter = meter.create_counter(
    "chaos.safety_triggers",
    description="Number of safety control triggers"
)


@dataclass
class ChaosScenario:
    """A chaos testing scenario."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: Optional[str] = None
    faults: List[FaultConfig] = field(default_factory=list)
    order: str = "sequential"  # sequential, parallel, random
    repeat_count: int = 1
    success_criteria: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> bool:
        """Validate scenario configuration."""
        if not self.faults:
            return False
        if self.order not in ["sequential", "parallel", "random"]:
            return False
        if self.repeat_count < 1:
            return False
        return True


@dataclass
class ChaosResult:
    """Result of a chaos experiment."""
    
    experiment_id: str
    scenario_id: Optional[str] = None
    status: ExperimentStatus = ExperimentStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # Fault results
    total_faults: int = 0
    successful_faults: int = 0
    failed_faults: int = 0
    skipped_faults: int = 0
    fault_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # Safety
    safety_triggered: bool = False
    safety_reasons: List[str] = field(default_factory=list)
    rollback_performed: bool = False
    
    # Metrics
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    # Steady state
    steady_state_before: Optional[bool] = None
    steady_state_after: Optional[bool] = None
    steady_state_details: Dict[str, Any] = field(default_factory=dict)
    
    # Errors
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "experiment_id": self.experiment_id,
            "scenario_id": self.scenario_id,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "total_faults": self.total_faults,
            "successful_faults": self.successful_faults,
            "failed_faults": self.failed_faults,
            "skipped_faults": self.skipped_faults,
            "fault_results": self.fault_results,
            "safety_triggered": self.safety_triggered,
            "safety_reasons": self.safety_reasons,
            "rollback_performed": self.rollback_performed,
            "metrics": self.metrics,
            "steady_state_before": self.steady_state_before,
            "steady_state_after": self.steady_state_after,
            "steady_state_details": self.steady_state_details,
            "errors": self.errors
        }


class SafetyController:
    """Safety controller for chaos experiments."""
    
    def __init__(self, config: SafetyConfig):
        self.config = config
        self.circuit_breaker_open = False
        self.circuit_breaker_failures = 0
        self.circuit_breaker_last_failure: Optional[datetime] = None
        self.emergency_stop_triggered = False
        self._protected_targets: Set[str] = set(config.protected_services + config.protected_hosts)
        
    async def check_safety(self, health_monitor: SystemHealthMonitor) -> Tuple[bool, List[str]]:
        """Check if it's safe to continue the experiment."""
        if not self.config.enabled:
            return True, []
        
        reasons = []
        
        # Check emergency stop
        if self.emergency_stop_triggered:
            reasons.append("Emergency stop triggered")
            return False, reasons
        
        # Check circuit breaker
        if self.circuit_breaker_open:
            if self.circuit_breaker_last_failure:
                elapsed = (datetime.now() - self.circuit_breaker_last_failure).total_seconds()
                if elapsed < self.config.circuit_breaker_timeout:
                    reasons.append(f"Circuit breaker open (wait {self.config.circuit_breaker_timeout - elapsed:.1f}s)")
                    return False, reasons
                else:
                    # Reset circuit breaker
                    self.circuit_breaker_open = False
                    self.circuit_breaker_failures = 0
                    logger.info("Circuit breaker reset")
        
        # Check health metrics
        metrics = await health_monitor.get_metrics()
        
        # Check error rate
        if metrics.get("error_rate", 0) > self.config.max_error_rate:
            reasons.append(f"Error rate too high: {metrics['error_rate']:.2%} > {self.config.max_error_rate:.2%}")
        
        # Check latency
        if metrics.get("latency_p99", 0) > self.config.max_latency_ms:
            reasons.append(f"Latency too high: {metrics['latency_p99']}ms > {self.config.max_latency_ms}ms")
        
        # Check success rate
        if metrics.get("success_rate", 1.0) < self.config.min_success_rate:
            reasons.append(f"Success rate too low: {metrics['success_rate']:.2%} < {self.config.min_success_rate:.2%}")
        
        # Trip circuit breaker if needed
        if reasons:
            self.circuit_breaker_failures += 1
            if self.circuit_breaker_failures >= 3:
                self.circuit_breaker_open = True
                self.circuit_breaker_last_failure = datetime.now()
                logger.warning("Circuit breaker tripped")
                safety_trigger_counter.add(1, {"type": "circuit_breaker"})
        
        return len(reasons) == 0, reasons
    
    def is_target_protected(self, target: str) -> bool:
        """Check if a target is protected from chaos."""
        return target in self._protected_targets
    
    def is_time_allowed(self) -> bool:
        """Check if current time is within allowed windows."""
        if not self.config.allowed_time_windows:
            return True
        
        now = datetime.now()
        for window in self.config.allowed_time_windows:
            start = datetime.fromisoformat(window.get("start", ""))
            end = datetime.fromisoformat(window.get("end", ""))
            if start <= now <= end:
                return True
        
        return False
    
    async def trigger_emergency_stop(self, reason: str) -> None:
        """Trigger emergency stop."""
        self.emergency_stop_triggered = True
        logger.critical(f"EMERGENCY STOP: {reason}")
        safety_trigger_counter.add(1, {"type": "emergency_stop"})
        
        # Notify emergency contacts
        if self.config.emergency_contacts:
            for contact in self.config.emergency_contacts:
                logger.info(f"Would notify emergency contact: {contact}")
    
    def calculate_blast_radius(self, targets: List[str]) -> bool:
        """Check if blast radius is within limits."""
        if len(targets) > self.config.max_affected_instances:
            return False
        
        # In production, would calculate percentage of total instances
        return True


class ExperimentRunner:
    """Runs individual chaos experiments."""
    
    def __init__(self):
        self.active_faults: List[FaultInjector] = []
        self.health_monitor = SystemHealthMonitor()
        self.fault_monitor = FaultMonitor()
        
    async def run_fault(
        self,
        fault_config: FaultConfig,
        safety_controller: SafetyController
    ) -> Dict[str, Any]:
        """Run a single fault injection."""
        
        # Check if target is protected
        if fault_config.target and safety_controller.is_target_protected(fault_config.target):
            logger.info(f"Skipping protected target: {fault_config.target}")
            return {
                "fault": fault_config.name,
                "status": "skipped",
                "reason": "protected_target"
            }
        
        # Create appropriate fault injector
        injector: Optional[FaultInjector] = None
        
        if isinstance(fault_config, NetworkFaultConfig):
            injector = NetworkFaultInjector(fault_config)
        elif isinstance(fault_config, ResourceFaultConfig):
            injector = ResourceFaultInjector(fault_config)
        elif fault_config.type in ["process_kill", "process_pause", "system_time_drift"]:
            injector = SystemFaultInjector(fault_config)
        elif fault_config.type in ["time_fault"]:
            injector = TimeFaultInjector(fault_config)
        else:
            logger.warning(f"Unknown fault type: {fault_config.type}")
            return {
                "fault": fault_config.name,
                "status": "failed",
                "error": f"Unknown fault type: {fault_config.type}"
            }
        
        # Run fault with monitoring
        result = {
            "fault": fault_config.name,
            "type": fault_config.type,
            "start_time": datetime.now().isoformat()
        }
        
        try:
            async with injector.injection_context() as injection_result:
                self.active_faults.append(injector)
                
                if injection_result.get("injected"):
                    result["status"] = "active"
                    result["injection_details"] = injection_result.get("result", {})
                    
                    # Monitor during injection
                    await self.fault_monitor.monitor_fault(
                        injector,
                        duration=fault_config.duration
                    )
                else:
                    result["status"] = "skipped"
                    result["reason"] = injection_result.get("reason", "unknown")
                
        except Exception as e:
            logger.error(f"Fault injection failed: {e}")
            result["status"] = "failed"
            result["error"] = str(e)
            
        finally:
            if injector in self.active_faults:
                self.active_faults.remove(injector)
            result["end_time"] = datetime.now().isoformat()
            
        return result
    
    async def cleanup_all_faults(self) -> None:
        """Clean up all active faults."""
        for injector in self.active_faults:
            try:
                await injector.cleanup()
            except Exception as e:
                logger.error(f"Failed to cleanup fault: {e}")
        self.active_faults.clear()


class ChaosOrchestrator:
    """Main orchestrator for chaos experiments."""
    
    def __init__(self):
        self.experiments: Dict[str, ChaosResult] = {}
        self.runner = ExperimentRunner()
        self._running_experiments: Set[str] = set()
    
    def validate_experiment(self, config: ChaosExperimentConfig) -> Tuple[bool, List[str]]:
        """
        Validate an experiment configuration before running.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check name and description
        if not config.name:
            errors.append("Experiment name is required")
        
        # Check faults
        if not config.faults:
            errors.append("At least one fault must be defined")
        
        # Validate each fault
        for i, fault in enumerate(config.faults):
            if not fault.name:
                errors.append(f"Fault {i} is missing a name")
            
            if fault.duration <= 0:
                errors.append(f"Fault '{fault.name}' has invalid duration: {fault.duration}")
            
            if hasattr(fault, 'probability'):
                if not 0 <= fault.probability <= 1:
                    errors.append(f"Fault '{fault.name}' has invalid probability: {fault.probability}")
        
        # Check safety config
        if config.safety:
            if config.safety.max_error_rate < 0 or config.safety.max_error_rate > 1:
                errors.append(f"Invalid max_error_rate: {config.safety.max_error_rate}")
            
            if config.safety.min_success_rate < 0 or config.safety.min_success_rate > 1:
                errors.append(f"Invalid min_success_rate: {config.safety.min_success_rate}")
            
            if config.safety.circuit_breaker_threshold < 0 or config.safety.circuit_breaker_threshold > 1:
                errors.append(f"Invalid circuit_breaker_threshold: {config.safety.circuit_breaker_threshold}")
        
        # Check timing
        if config.start_delay < 0:
            errors.append(f"Invalid start_delay: {config.start_delay}")
        
        if config.max_duration and config.max_duration <= 0:
            errors.append(f"Invalid max_duration: {config.max_duration}")
        
        return len(errors) == 0, errors
        
    async def run_experiment(
        self,
        config: ChaosExperimentConfig,
        sandbox_id: Optional[str] = None
    ) -> ChaosResult:
        """Run a complete chaos experiment."""
        
        experiment_id = str(uuid.uuid4())
        result = ChaosResult(experiment_id=experiment_id)
        
        # Check if already running
        if experiment_id in self._running_experiments:
            result.status = ExperimentStatus.FAILED
            result.errors.append("Experiment already running")
            return result
        
        self._running_experiments.add(experiment_id)
        span = tracer.start_span(f"chaos_experiment.{config.name}")
        
        try:
            # Initialize
            result.status = ExperimentStatus.RUNNING
            result.start_time = datetime.now()
            safety_controller = SafetyController(config.safety)
            
            logger.info(f"Starting chaos experiment: {config.name} (ID: {experiment_id})")
            experiment_counter.add(1, {"name": config.name})
            
            # Apply start delay
            if config.start_delay > 0:
                logger.info(f"Waiting {config.start_delay}s before starting")
                await asyncio.sleep(config.start_delay)
            
            # Check time window
            if not safety_controller.is_time_allowed():
                result.status = ExperimentStatus.ABORTED
                result.errors.append("Outside allowed time window")
                return result
            
            # Check steady state hypothesis (before)
            if config.steady_state_checks:
                result.steady_state_before = await self._check_steady_state(
                    config.steady_state_checks
                )
                if not result.steady_state_before and not config.dry_run:
                    result.status = ExperimentStatus.FAILED
                    result.errors.append("Steady state check failed before experiment")
                    return result
            
            # Prepare faults
            faults = config.faults.copy()
            if config.randomize_order:
                random.shuffle(faults)
            
            # Run faults
            result.total_faults = len(faults)
            
            if config.parallel_execution:
                # Run faults in parallel
                tasks = []
                for fault in faults:
                    if config.dry_run:
                        logger.info(f"[DRY RUN] Would inject: {fault.name}")
                        result.skipped_faults += 1
                    else:
                        task = self.runner.run_fault(fault, safety_controller)
                        tasks.append(task)
                
                if tasks:
                    fault_results = await asyncio.gather(*tasks, return_exceptions=True)
                    for fault_result in fault_results:
                        if isinstance(fault_result, Exception):
                            result.failed_faults += 1
                            result.errors.append(str(fault_result))
                        else:
                            result.fault_results.append(fault_result)
                            if fault_result.get("status") == "active":
                                result.successful_faults += 1
                            elif fault_result.get("status") == "skipped":
                                result.skipped_faults += 1
                            else:
                                result.failed_faults += 1
            else:
                # Run faults sequentially
                for i, fault in enumerate(faults):
                    # Check safety before each fault
                    safe, reasons = await safety_controller.check_safety(self.runner.health_monitor)
                    if not safe:
                        logger.warning(f"Safety check failed: {reasons}")
                        result.safety_triggered = True
                        result.safety_reasons.extend(reasons)
                        
                        if config.safety.auto_rollback:
                            await self._perform_rollback(config, result)
                        break
                    
                    if config.dry_run:
                        logger.info(f"[DRY RUN] Would inject: {fault.name}")
                        result.skipped_faults += 1
                    else:
                        fault_result = await self.runner.run_fault(fault, safety_controller)
                        result.fault_results.append(fault_result)
                        
                        if fault_result.get("status") == "active":
                            result.successful_faults += 1
                        elif fault_result.get("status") == "skipped":
                            result.skipped_faults += 1
                        else:
                            result.failed_faults += 1
                    
                    # Apply cooldown between faults
                    if i < len(faults) - 1 and config.cooldown_period > 0:
                        await asyncio.sleep(config.cooldown_period)
            
            # Check steady state hypothesis (after)
            if config.steady_state_checks and not config.dry_run:
                result.steady_state_after = await self._check_steady_state(
                    config.steady_state_checks
                )
            
            # Collect final metrics
            result.metrics = await self.runner.health_monitor.get_metrics()
            
            # Determine final status
            if result.safety_triggered:
                result.status = ExperimentStatus.ABORTED
            elif result.failed_faults > 0:
                result.status = ExperimentStatus.FAILED
            else:
                result.status = ExperimentStatus.COMPLETED
            
        except Exception as e:
            logger.error(f"Experiment failed: {e}")
            result.status = ExperimentStatus.FAILED
            result.errors.append(str(e))
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            
        finally:
            # Cleanup
            await self.runner.cleanup_all_faults()
            
            result.end_time = datetime.now()
            result.duration_seconds = (result.end_time - result.start_time).total_seconds()
            
            self._running_experiments.discard(experiment_id)
            self.experiments[experiment_id] = result
            
            experiment_duration.record(
                result.duration_seconds,
                {"name": config.name, "status": result.status}
            )
            
            span.set_attribute("experiment.id", experiment_id)
            span.set_attribute("experiment.status", result.status)
            span.set_attribute("experiment.total_faults", result.total_faults)
            span.set_attribute("experiment.successful_faults", result.successful_faults)
            span.end()
            
            # Send notifications
            if config.notify_on_complete and result.status == ExperimentStatus.COMPLETED:
                await self._send_notification(config, result, "completed")
            elif config.notify_on_failure and result.status in [ExperimentStatus.FAILED, ExperimentStatus.ABORTED]:
                await self._send_notification(config, result, "failed")
            
            logger.info(f"Chaos experiment completed: {result.status} (ID: {experiment_id})")
            
        return result
    
    async def run_scenario(
        self,
        scenario: ChaosScenario,
        config: ChaosExperimentConfig
    ) -> List[ChaosResult]:
        """Run a chaos scenario (potentially multiple times)."""
        
        if not scenario.validate():
            raise ValueError(f"Invalid scenario: {scenario.name}")
        
        results = []
        
        for i in range(scenario.repeat_count):
            logger.info(f"Running scenario iteration {i+1}/{scenario.repeat_count}")
            
            # Update config with scenario faults
            scenario_config = config.model_copy()
            scenario_config.faults = scenario.faults
            scenario_config.parallel_execution = scenario.order == "parallel"
            scenario_config.randomize_order = scenario.order == "random"
            
            result = await self.run_experiment(scenario_config)
            result.scenario_id = scenario.id
            results.append(result)
            
            # Check success criteria
            if scenario.success_criteria:
                if not self._check_success_criteria(result, scenario.success_criteria):
                    logger.warning(f"Scenario failed success criteria at iteration {i+1}")
                    break
        
        return results
    
    async def _check_steady_state(self, checks: List[Dict[str, Any]]) -> bool:
        """Check steady state hypothesis."""
        for check in checks:
            check_type = check.get("type")
            
            if check_type == "http_health":
                # Check HTTP endpoint health
                url = check.get("url")
                expected_status = check.get("expected_status", 200)
                # In production, make HTTP request and check status
                logger.info(f"Would check HTTP health: {url} expecting {expected_status}")
                
            elif check_type == "metric_threshold":
                # Check metric threshold
                metric_name = check.get("metric")
                threshold = check.get("threshold")
                operator = check.get("operator", "lt")  # lt, gt, eq
                # In production, query metrics and compare
                logger.info(f"Would check metric: {metric_name} {operator} {threshold}")
                
            elif check_type == "custom":
                # Run custom check
                logger.info("Would run custom steady state check")
        
        return True  # Simplified for demo
    
    async def _perform_rollback(
        self,
        config: ChaosExperimentConfig,
        result: ChaosResult
    ) -> None:
        """Perform rollback actions."""
        logger.info("Performing rollback...")
        result.rollback_performed = True
        
        # Clean up all active faults
        await self.runner.cleanup_all_faults()
        
        # Execute rollback plan if provided
        if config.rollback_plan:
            for action in config.rollback_plan.get("actions", []):
                action_type = action.get("type")
                
                if action_type == "restart_service":
                    service = action.get("service")
                    logger.info(f"Would restart service: {service}")
                elif action_type == "restore_config":
                    config_path = action.get("path")
                    logger.info(f"Would restore config: {config_path}")
                elif action_type == "custom":
                    logger.info("Would execute custom rollback action")
    
    async def _send_notification(
        self,
        config: ChaosExperimentConfig,
        result: ChaosResult,
        event: str
    ) -> None:
        """Send notifications about experiment events."""
        for channel in config.notification_channels:
            if channel == "webhook":
                # Send webhook notification
                logger.info(f"Would send webhook notification for {event}")
            elif channel == "email":
                # Send email notification
                logger.info(f"Would send email notification for {event}")
            elif channel == "slack":
                # Send Slack notification
                logger.info(f"Would send Slack notification for {event}")
    
    def _check_success_criteria(
        self,
        result: ChaosResult,
        criteria: Dict[str, Any]
    ) -> bool:
        """Check if result meets success criteria."""
        for key, expected_value in criteria.items():
            if key == "min_success_rate":
                actual = result.successful_faults / max(result.total_faults, 1)
                if actual < expected_value:
                    return False
            elif key == "max_errors":
                if len(result.errors) > expected_value:
                    return False
            elif key == "steady_state_maintained":
                if expected_value and not (result.steady_state_before and result.steady_state_after):
                    return False
        
        return True
    
    def get_experiment_status(self, experiment_id: str) -> Optional[ChaosResult]:
        """Get status of an experiment."""
        return self.experiments.get(experiment_id)
    
    def list_experiments(self) -> List[Dict[str, Any]]:
        """List all experiments."""
        return [
            {
                "id": exp_id,
                "status": result.status,
                "start_time": result.start_time.isoformat() if result.start_time else None,
                "duration": result.duration_seconds
            }
            for exp_id, result in self.experiments.items()
        ]