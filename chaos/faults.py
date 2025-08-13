"""Fault injection implementations for chaos engineering."""

import asyncio
import random
import time
import os
import signal
import psutil
import subprocess
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import logging

from opentelemetry import trace, metrics
from opentelemetry.trace import Status, StatusCode

from .config import (
    FaultConfig, NetworkFaultConfig, ResourceFaultConfig,
    FaultType, NetworkFaultType, ResourceType
)


logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Create metrics
fault_injection_counter = meter.create_counter(
    "chaos.fault_injections",
    description="Number of fault injections"
)
fault_duration_histogram = meter.create_histogram(
    "chaos.fault_duration",
    description="Duration of fault injections",
    unit="s"
)
fault_error_counter = meter.create_counter(
    "chaos.fault_errors",
    description="Number of fault injection errors"
)


class FaultInjector(ABC):
    """Abstract base class for fault injectors."""
    
    def __init__(self, config: FaultConfig):
        self.config = config
        self.is_active = False
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self._cleanup_tasks: List[Callable] = []
        
    @abstractmethod
    async def inject(self) -> Dict[str, Any]:
        """Inject the fault."""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up after fault injection."""
        pass
    
    async def should_inject(self) -> bool:
        """Determine if fault should be injected based on probability."""
        return random.random() < self.config.probability
    
    @asynccontextmanager
    async def injection_context(self):
        """Context manager for fault injection with automatic cleanup."""
        span = tracer.start_span(f"fault_injection.{self.config.type}")
        
        try:
            # Check probability
            if not await self.should_inject():
                span.add_event("Fault injection skipped (probability)")
                yield {"injected": False, "reason": "probability"}
                return
            
            # Apply delay if configured
            if self.config.delay > 0:
                logger.info(f"Delaying fault injection by {self.config.delay}s")
                await asyncio.sleep(self.config.delay)
            
            # Inject fault
            self.is_active = True
            self.start_time = datetime.now()
            
            fault_injection_counter.add(1, {"fault_type": self.config.type})
            span.set_attribute("fault.type", self.config.type)
            span.set_attribute("fault.name", self.config.name)
            span.set_attribute("fault.duration", self.config.duration)
            
            result = await self.inject()
            span.add_event("Fault injected", {"result": str(result)})
            
            yield {"injected": True, "result": result, "start_time": self.start_time}
            
            # Wait for duration
            if self.config.duration > 0:
                await asyncio.sleep(self.config.duration)
            
        except Exception as e:
            logger.error(f"Error during fault injection: {e}")
            fault_error_counter.add(1, {"fault_type": self.config.type})
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            raise
            
        finally:
            # Cleanup
            self.is_active = False
            self.end_time = datetime.now()
            
            if self.start_time:
                duration = (self.end_time - self.start_time).total_seconds()
                fault_duration_histogram.record(duration, {"fault_type": self.config.type})
            
            try:
                await self.cleanup()
                span.add_event("Fault cleaned up")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
                span.record_exception(e)
            
            span.end()


class NetworkFaultInjector(FaultInjector):
    """Inject network-related faults."""
    
    def __init__(self, config: NetworkFaultConfig):
        super().__init__(config)
        self.config: NetworkFaultConfig = config
        self._tc_rules: List[str] = []
        self._iptables_rules: List[str] = []
        
    async def inject(self) -> Dict[str, Any]:
        """Inject network fault using tc (traffic control) and iptables."""
        result = {}
        
        if self.config.network_type == NetworkFaultType.LATENCY:
            result = await self._inject_latency()
        elif self.config.network_type == NetworkFaultType.PACKET_LOSS:
            result = await self._inject_packet_loss()
        elif self.config.network_type == NetworkFaultType.BANDWIDTH_LIMIT:
            result = await self._inject_bandwidth_limit()
        elif self.config.network_type == NetworkFaultType.PARTITION:
            result = await self._inject_partition()
        elif self.config.network_type == NetworkFaultType.DNS_FAILURE:
            result = await self._inject_dns_failure()
        else:
            logger.warning(f"Unsupported network fault type: {self.config.network_type}")
            
        return result
    
    async def _inject_latency(self) -> Dict[str, Any]:
        """Inject network latency using tc."""
        interface = self.config.interface or "eth0"
        latency = self.config.latency_ms or 100
        jitter = self.config.jitter_ms or 10
        
        # Create tc qdisc
        commands = [
            f"tc qdisc add dev {interface} root netem delay {latency}ms {jitter}ms"
        ]
        
        if self.config.correlation:
            commands[0] += f" {int(self.config.correlation * 100)}%"
        
        for cmd in commands:
            try:
                # In production, this would execute the command
                # For safety in demo, we just log it
                logger.info(f"Would execute: {cmd}")
                self._tc_rules.append(cmd)
            except Exception as e:
                logger.error(f"Failed to inject latency: {e}")
                
        return {
            "type": "latency",
            "interface": interface,
            "latency_ms": latency,
            "jitter_ms": jitter
        }
    
    async def _inject_packet_loss(self) -> Dict[str, Any]:
        """Inject packet loss using tc."""
        interface = self.config.interface or "eth0"
        loss = self.config.loss_percentage or 5.0
        
        cmd = f"tc qdisc add dev {interface} root netem loss {loss}%"
        
        if self.config.loss_correlation:
            cmd += f" {int(self.config.loss_correlation * 100)}%"
        
        try:
            logger.info(f"Would execute: {cmd}")
            self._tc_rules.append(cmd)
        except Exception as e:
            logger.error(f"Failed to inject packet loss: {e}")
            
        return {
            "type": "packet_loss",
            "interface": interface,
            "loss_percentage": loss
        }
    
    async def _inject_bandwidth_limit(self) -> Dict[str, Any]:
        """Inject bandwidth limitation using tc."""
        interface = self.config.interface or "eth0"
        limit = self.config.bandwidth_limit_mbps or 1.0
        
        commands = [
            f"tc qdisc add dev {interface} root handle 1: htb default 30",
            f"tc class add dev {interface} parent 1: classid 1:1 htb rate {limit}mbit",
            f"tc class add dev {interface} parent 1:1 classid 1:30 htb rate {limit}mbit"
        ]
        
        for cmd in commands:
            try:
                logger.info(f"Would execute: {cmd}")
                self._tc_rules.append(cmd)
            except Exception as e:
                logger.error(f"Failed to inject bandwidth limit: {e}")
                
        return {
            "type": "bandwidth_limit",
            "interface": interface,
            "limit_mbps": limit
        }
    
    async def _inject_partition(self) -> Dict[str, Any]:
        """Inject network partition using iptables."""
        targets = self.config.target_hosts or []
        
        for target in targets:
            # Block incoming and outgoing traffic
            for chain, direction in [("INPUT", "src"), ("OUTPUT", "dst")]:
                cmd = f"iptables -A {chain} -{direction[0]} {target} -j DROP"
                try:
                    logger.info(f"Would execute: {cmd}")
                    self._iptables_rules.append(cmd)
                except Exception as e:
                    logger.error(f"Failed to inject partition: {e}")
                    
        return {
            "type": "partition",
            "blocked_hosts": targets
        }
    
    async def _inject_dns_failure(self) -> Dict[str, Any]:
        """Inject DNS failures by blocking DNS traffic."""
        commands = [
            "iptables -A OUTPUT -p udp --dport 53 -j DROP",
            "iptables -A OUTPUT -p tcp --dport 53 -j DROP"
        ]
        
        for cmd in commands:
            try:
                logger.info(f"Would execute: {cmd}")
                self._iptables_rules.append(cmd)
            except Exception as e:
                logger.error(f"Failed to inject DNS failure: {e}")
                
        return {
            "type": "dns_failure",
            "blocked_ports": [53]
        }
    
    async def cleanup(self) -> None:
        """Clean up network fault injections."""
        # Clean up tc rules
        for rule in self._tc_rules:
            if "add" in rule:
                cleanup_cmd = rule.replace("add", "del")
                try:
                    logger.info(f"Would execute cleanup: {cleanup_cmd}")
                except Exception as e:
                    logger.error(f"Failed to cleanup tc rule: {e}")
        
        # Clean up iptables rules
        for rule in self._iptables_rules:
            if "-A" in rule:
                cleanup_cmd = rule.replace("-A", "-D")
                try:
                    logger.info(f"Would execute cleanup: {cleanup_cmd}")
                except Exception as e:
                    logger.error(f"Failed to cleanup iptables rule: {e}")
        
        self._tc_rules.clear()
        self._iptables_rules.clear()


class ResourceFaultInjector(FaultInjector):
    """Inject resource pressure faults."""
    
    def __init__(self, config: ResourceFaultConfig):
        super().__init__(config)
        self.config: ResourceFaultConfig = config
        self._stress_processes: List[subprocess.Popen] = []
        self._allocated_resources: List[Any] = []
        
    async def inject(self) -> Dict[str, Any]:
        """Inject resource pressure."""
        result = {}
        
        if self.config.resource_type == ResourceType.CPU:
            result = await self._inject_cpu_pressure()
        elif self.config.resource_type == ResourceType.MEMORY:
            result = await self._inject_memory_pressure()
        elif self.config.resource_type == ResourceType.DISK:
            result = await self._inject_disk_pressure()
        elif self.config.resource_type == ResourceType.FILE_DESCRIPTORS:
            result = await self._inject_fd_exhaustion()
        else:
            logger.warning(f"Unsupported resource type: {self.config.resource_type}")
            
        return result
    
    async def _inject_cpu_pressure(self) -> Dict[str, Any]:
        """Inject CPU pressure using stress-ng or Python loops."""
        cores = self.config.cpu_cores or 1
        percentage = self.config.cpu_percentage or 80.0
        
        # For demo, simulate CPU pressure
        async def cpu_burn():
            """Burn CPU cycles."""
            start = time.time()
            while time.time() - start < self.config.duration:
                # Busy loop to consume CPU
                _ = sum(i * i for i in range(10000))
                # Yield to allow other tasks
                if int(time.time()) % 10 == 0:
                    await asyncio.sleep(0.001)
        
        # Create tasks for each core
        for _ in range(cores):
            task = asyncio.create_task(cpu_burn())
            self._cleanup_tasks.append(lambda: task.cancel())
        
        return {
            "type": "cpu_pressure",
            "cores": cores,
            "percentage": percentage
        }
    
    async def _inject_memory_pressure(self) -> Dict[str, Any]:
        """Inject memory pressure by allocating memory."""
        memory_mb = self.config.memory_mb or 100
        
        try:
            # Allocate memory (in production, use more sophisticated methods)
            chunk_size = 1024 * 1024  # 1 MB
            chunks = []
            
            for _ in range(memory_mb):
                # Allocate and hold memory
                chunk = bytearray(chunk_size)
                # Touch memory to ensure allocation
                for i in range(0, chunk_size, 4096):
                    chunk[i] = 1
                chunks.append(chunk)
                self._allocated_resources.append(chunk)
                
            logger.info(f"Allocated {memory_mb} MB of memory")
            
        except MemoryError as e:
            logger.error(f"Failed to allocate memory: {e}")
            
        return {
            "type": "memory_pressure",
            "allocated_mb": memory_mb
        }
    
    async def _inject_disk_pressure(self) -> Dict[str, Any]:
        """Inject disk I/O pressure."""
        disk_size_mb = self.config.disk_size_mb or 100
        disk_path = self.config.disk_path or "/tmp"
        
        file_path = os.path.join(disk_path, f"chaos_disk_{int(time.time())}.tmp")
        
        try:
            # Write large file to disk
            chunk_size = 1024 * 1024  # 1 MB
            with open(file_path, 'wb') as f:
                for _ in range(disk_size_mb):
                    data = os.urandom(chunk_size)
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
            
            self._allocated_resources.append(file_path)
            logger.info(f"Created {disk_size_mb} MB file at {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to create disk pressure: {e}")
            
        return {
            "type": "disk_pressure",
            "file_path": file_path,
            "size_mb": disk_size_mb
        }
    
    async def _inject_fd_exhaustion(self) -> Dict[str, Any]:
        """Inject file descriptor exhaustion."""
        fd_count = self.config.fd_count or 1000
        fd_type = self.config.fd_type or "file"
        
        fds = []
        try:
            for i in range(fd_count):
                if fd_type == "file":
                    # Open temporary files
                    f = open(f"/tmp/chaos_fd_{i}.tmp", 'w')
                    fds.append(f)
                    self._allocated_resources.append(f)
                elif fd_type == "socket":
                    # Create sockets (simplified for demo)
                    import socket
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    fds.append(s)
                    self._allocated_resources.append(s)
                    
            logger.info(f"Opened {len(fds)} file descriptors")
            
        except Exception as e:
            logger.error(f"Failed to exhaust file descriptors: {e}")
            
        return {
            "type": "fd_exhaustion",
            "count": len(fds),
            "fd_type": fd_type
        }
    
    async def cleanup(self) -> None:
        """Clean up resource allocations."""
        # Cancel CPU burn tasks
        for cleanup_task in self._cleanup_tasks:
            try:
                cleanup_task()
            except Exception as e:
                logger.error(f"Failed to cleanup task: {e}")
        
        # Clean up allocated resources
        for resource in self._allocated_resources:
            try:
                if isinstance(resource, str) and os.path.exists(resource):
                    # Remove file
                    os.remove(resource)
                elif hasattr(resource, 'close'):
                    # Close file descriptor or socket
                    resource.close()
            except Exception as e:
                logger.error(f"Failed to cleanup resource: {e}")
        
        # Kill stress processes
        for process in self._stress_processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception as e:
                logger.error(f"Failed to terminate stress process: {e}")
        
        self._cleanup_tasks.clear()
        self._allocated_resources.clear()
        self._stress_processes.clear()


class SystemFaultInjector(FaultInjector):
    """Inject system-level faults."""
    
    async def inject(self) -> Dict[str, Any]:
        """Inject system fault."""
        if self.config.type == FaultType.PROCESS_KILL:
            return await self._inject_process_kill()
        elif self.config.type == FaultType.PROCESS_PAUSE:
            return await self._inject_process_pause()
        elif self.config.type == FaultType.SYSTEM_TIME_DRIFT:
            return await self._inject_time_drift()
        else:
            logger.warning(f"Unsupported system fault type: {self.config.type}")
            return {}
    
    async def _inject_process_kill(self) -> Dict[str, Any]:
        """Kill a target process."""
        target = self.config.target
        
        if not target:
            logger.warning("No target specified for process kill")
            return {"type": "process_kill", "killed": False}
        
        try:
            # Find process by name
            for proc in psutil.process_iter(['pid', 'name']):
                if target in proc.info['name']:
                    logger.info(f"Would kill process: {proc.info['name']} (PID: {proc.info['pid']})")
                    # In production: proc.kill()
                    return {
                        "type": "process_kill",
                        "process": proc.info['name'],
                        "pid": proc.info['pid'],
                        "killed": True
                    }
        except Exception as e:
            logger.error(f"Failed to kill process: {e}")
            
        return {"type": "process_kill", "killed": False}
    
    async def _inject_process_pause(self) -> Dict[str, Any]:
        """Pause a target process using SIGSTOP."""
        target = self.config.target
        
        if not target:
            logger.warning("No target specified for process pause")
            return {"type": "process_pause", "paused": False}
        
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if target in proc.info['name']:
                    logger.info(f"Would pause process: {proc.info['name']} (PID: {proc.info['pid']})")
                    # In production: os.kill(proc.info['pid'], signal.SIGSTOP)
                    self._cleanup_tasks.append(
                        lambda pid=proc.info['pid']: os.kill(pid, signal.SIGCONT)
                    )
                    return {
                        "type": "process_pause",
                        "process": proc.info['name'],
                        "pid": proc.info['pid'],
                        "paused": True
                    }
        except Exception as e:
            logger.error(f"Failed to pause process: {e}")
            
        return {"type": "process_pause", "paused": False}
    
    async def _inject_time_drift(self) -> Dict[str, Any]:
        """Inject system time drift."""
        drift_seconds = self.config.metadata.get("drift_seconds", 60)
        
        try:
            # In production, this would adjust system time
            # For safety, we just log the action
            logger.info(f"Would adjust system time by {drift_seconds} seconds")
            
            return {
                "type": "time_drift",
                "drift_seconds": drift_seconds,
                "applied": True
            }
        except Exception as e:
            logger.error(f"Failed to inject time drift: {e}")
            return {"type": "time_drift", "applied": False}
    
    async def cleanup(self) -> None:
        """Clean up system faults."""
        for cleanup_task in self._cleanup_tasks:
            try:
                cleanup_task()
            except Exception as e:
                logger.error(f"Failed to cleanup: {e}")
        self._cleanup_tasks.clear()


class TimeFaultInjector(FaultInjector):
    """Inject time-related faults for testing time-sensitive operations."""
    
    def __init__(self, config: FaultConfig):
        super().__init__(config)
        self._original_time = None
        self._time_offset = 0
        
    async def inject(self) -> Dict[str, Any]:
        """Inject time fault by mocking time functions."""
        drift_type = self.config.metadata.get("drift_type", "forward")
        drift_amount = self.config.metadata.get("drift_amount", 3600)  # 1 hour default
        
        if drift_type == "forward":
            self._time_offset = drift_amount
        elif drift_type == "backward":
            self._time_offset = -drift_amount
        elif drift_type == "freeze":
            self._time_offset = 0
            # Freeze time at current moment
            
        logger.info(f"Injecting time drift: {drift_type} by {drift_amount} seconds")
        
        return {
            "type": "time_fault",
            "drift_type": drift_type,
            "drift_amount": drift_amount,
            "offset": self._time_offset
        }
    
    async def cleanup(self) -> None:
        """Reset time modifications."""
        self._time_offset = 0
        logger.info("Time fault cleaned up")