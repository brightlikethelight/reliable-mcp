"""Configuration models for chaos engineering and fault injection."""

from enum import Enum
from typing import Dict, List, Optional, Any, Union
from datetime import timedelta
from pydantic import BaseModel, Field, field_validator


class FaultType(str, Enum):
    """Types of faults that can be injected."""
    
    # Network faults
    NETWORK_LATENCY = "network_latency"
    NETWORK_PACKET_LOSS = "network_packet_loss"
    NETWORK_PARTITION = "network_partition"
    NETWORK_BANDWIDTH_LIMIT = "network_bandwidth_limit"
    NETWORK_DNS_FAILURE = "network_dns_failure"
    
    # Resource faults
    CPU_PRESSURE = "cpu_pressure"
    MEMORY_PRESSURE = "memory_pressure"
    DISK_PRESSURE = "disk_pressure"
    IO_PRESSURE = "io_pressure"
    FILE_DESCRIPTOR_EXHAUSTION = "fd_exhaustion"
    
    # System faults
    PROCESS_KILL = "process_kill"
    PROCESS_PAUSE = "process_pause"
    SYSTEM_TIME_DRIFT = "system_time_drift"
    KERNEL_PANIC = "kernel_panic"
    
    # Application faults
    EXCEPTION_INJECTION = "exception_injection"
    TIMEOUT_INJECTION = "timeout_injection"
    ERROR_RESPONSE = "error_response"
    CORRUPT_DATA = "corrupt_data"


class NetworkFaultType(str, Enum):
    """Specific network fault types."""
    
    LATENCY = "latency"
    JITTER = "jitter"
    PACKET_LOSS = "packet_loss"
    PACKET_CORRUPTION = "packet_corruption"
    PACKET_DUPLICATION = "packet_duplication"
    PACKET_REORDERING = "packet_reordering"
    BANDWIDTH_LIMIT = "bandwidth_limit"
    CONNECTION_RESET = "connection_reset"
    DNS_FAILURE = "dns_failure"
    PARTITION = "partition"


class ResourceType(str, Enum):
    """Types of system resources."""
    
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    FILE_DESCRIPTORS = "file_descriptors"
    THREADS = "threads"
    PROCESSES = "processes"


class ExperimentStatus(str, Enum):
    """Status of chaos experiments."""
    
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"
    ROLLED_BACK = "rolled_back"


class FaultConfig(BaseModel):
    """Base configuration for fault injection."""
    
    type: FaultType
    name: str = Field(..., description="Human-readable fault name")
    description: Optional[str] = None
    probability: float = Field(1.0, ge=0.0, le=1.0, description="Probability of injection")
    duration: int = Field(60, description="Duration in seconds")
    delay: int = Field(0, description="Delay before injection in seconds")
    target: Optional[str] = Field(None, description="Target component/service")
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator("duration")
    def validate_duration(cls, v):
        if v < 0:
            raise ValueError("Duration must be non-negative")
        if v > 3600:  # 1 hour max
            raise ValueError("Duration cannot exceed 3600 seconds")
        return v


class NetworkFaultConfig(FaultConfig):
    """Configuration for network fault injection."""
    
    network_type: NetworkFaultType
    
    # Latency configuration
    latency_ms: Optional[int] = Field(None, ge=0, le=60000)
    jitter_ms: Optional[int] = Field(None, ge=0, le=10000)
    correlation: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    # Packet loss configuration
    loss_percentage: Optional[float] = Field(None, ge=0.0, le=100.0)
    loss_correlation: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    # Bandwidth configuration
    bandwidth_limit_mbps: Optional[float] = Field(None, ge=0.001, le=10000.0)
    
    # Target configuration
    target_hosts: List[str] = Field(default_factory=list)
    target_ports: List[int] = Field(default_factory=list)
    target_protocols: List[str] = Field(default_factory=lambda: ["tcp", "udp"])
    
    # Interface configuration
    interface: Optional[str] = Field(None, description="Network interface to affect")
    direction: str = Field("both", pattern="^(inbound|outbound|both)$")


class ResourceFaultConfig(FaultConfig):
    """Configuration for resource pressure injection."""
    
    resource_type: ResourceType
    
    # CPU configuration
    cpu_cores: Optional[int] = Field(None, ge=1, le=256)
    cpu_percentage: Optional[float] = Field(None, ge=0.0, le=100.0)
    
    # Memory configuration
    memory_mb: Optional[int] = Field(None, ge=1, le=1048576)  # Max 1TB
    memory_percentage: Optional[float] = Field(None, ge=0.0, le=100.0)
    memory_pattern: Optional[str] = Field("random", pattern="^(random|sequential|hot)$")
    
    # Disk configuration
    disk_size_mb: Optional[int] = Field(None, ge=1, le=1048576)
    disk_io_percentage: Optional[float] = Field(None, ge=0.0, le=100.0)
    disk_path: Optional[str] = Field("/tmp", description="Path for disk operations")
    
    # File descriptor configuration
    fd_count: Optional[int] = Field(None, ge=1, le=65536)
    fd_type: Optional[str] = Field("file", pattern="^(file|socket|pipe)$")
    
    # Process/thread configuration
    process_count: Optional[int] = Field(None, ge=1, le=10000)
    thread_count: Optional[int] = Field(None, ge=1, le=100000)


class SafetyConfig(BaseModel):
    """Safety controls for chaos experiments."""
    
    enabled: bool = Field(True, description="Enable safety controls")
    
    # Abort conditions
    max_error_rate: float = Field(0.5, ge=0.0, le=1.0)
    max_latency_ms: int = Field(10000, ge=0)
    min_success_rate: float = Field(0.5, ge=0.0, le=1.0)
    
    # Health checks
    health_check_interval: int = Field(10, description="Seconds between health checks")
    health_check_timeout: int = Field(5, description="Health check timeout in seconds")
    health_check_retries: int = Field(3, ge=1, le=10)
    
    # Circuit breaker
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: float = Field(0.5, ge=0.0, le=1.0)
    circuit_breaker_timeout: int = Field(60, description="Circuit breaker timeout in seconds")
    
    # Rollback
    auto_rollback: bool = Field(True, description="Automatically rollback on failure")
    rollback_timeout: int = Field(30, description="Rollback timeout in seconds")
    
    # Blast radius
    max_affected_instances: int = Field(1, ge=1)
    max_affected_percentage: float = Field(0.33, ge=0.0, le=1.0)
    
    # Emergency stop
    emergency_stop_enabled: bool = True
    emergency_contacts: List[str] = Field(default_factory=list)
    
    # Monitoring
    alert_enabled: bool = True
    alert_channels: List[str] = Field(default_factory=lambda: ["logs", "metrics"])
    
    # Whitelist/Blacklist
    protected_services: List[str] = Field(default_factory=list)
    protected_hosts: List[str] = Field(default_factory=list)
    allowed_time_windows: List[Dict[str, str]] = Field(default_factory=list)


class ChaosExperimentConfig(BaseModel):
    """Configuration for a complete chaos experiment."""
    
    name: str = Field(..., description="Experiment name")
    description: Optional[str] = None
    version: str = Field("1.0.0")
    
    # Experiment settings
    dry_run: bool = Field(False, description="Run without actual fault injection")
    parallel_execution: bool = Field(False, description="Run faults in parallel")
    randomize_order: bool = Field(False, description="Randomize fault execution order")
    
    # Timing
    start_delay: int = Field(0, description="Delay before starting in seconds")
    total_duration: int = Field(300, description="Total experiment duration in seconds")
    cooldown_period: int = Field(30, description="Cooldown between faults in seconds")
    
    # Faults
    faults: List[Union[NetworkFaultConfig, ResourceFaultConfig, FaultConfig]]
    
    # Targets
    target_services: List[str] = Field(default_factory=list)
    target_namespaces: List[str] = Field(default_factory=list)
    target_sandboxes: List[str] = Field(default_factory=list)
    
    # Safety
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    
    # Steady state hypothesis
    steady_state_checks: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Rollback plan
    rollback_plan: Optional[Dict[str, Any]] = None
    
    # Notifications
    notify_on_start: bool = False
    notify_on_complete: bool = True
    notify_on_failure: bool = True
    notification_channels: List[str] = Field(default_factory=list)
    
    # Metadata
    tags: List[str] = Field(default_factory=list)
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator("faults")
    def validate_faults(cls, v):
        if not v:
            raise ValueError("At least one fault must be specified")
        if len(v) > 100:
            raise ValueError("Maximum 100 faults per experiment")
        return v
    
    @field_validator("total_duration")
    def validate_total_duration(cls, v):
        if v < 1:
            raise ValueError("Total duration must be at least 1 second")
        if v > 86400:  # 24 hours
            raise ValueError("Total duration cannot exceed 24 hours")
        return v


class ChaosSchedule(BaseModel):
    """Schedule for recurring chaos experiments."""
    
    enabled: bool = True
    cron_expression: Optional[str] = Field(None, description="Cron expression for scheduling")
    interval_minutes: Optional[int] = Field(None, ge=1, le=10080)  # Max 1 week
    
    # Time windows
    allowed_days: List[str] = Field(
        default_factory=lambda: ["monday", "tuesday", "wednesday", "thursday", "friday"]
    )
    allowed_hours: List[int] = Field(
        default_factory=lambda: list(range(9, 17))  # 9 AM to 5 PM
    )
    
    # Limits
    max_experiments_per_day: int = Field(10, ge=1, le=100)
    min_interval_between_experiments: int = Field(60, description="Minutes between experiments")
    
    # Auto-scaling
    scale_with_traffic: bool = False
    traffic_threshold: float = Field(0.8, ge=0.0, le=1.0)
    
    @field_validator("allowed_days")
    def validate_days(cls, v):
        valid_days = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
        for day in v:
            if day.lower() not in valid_days:
                raise ValueError(f"Invalid day: {day}")
        return [d.lower() for d in v]
    
    @field_validator("allowed_hours")
    def validate_hours(cls, v):
        for hour in v:
            if not 0 <= hour <= 23:
                raise ValueError(f"Invalid hour: {hour}")
        return v