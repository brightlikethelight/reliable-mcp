"""
MCP Reliability Lab Benchmarking Module.
Provides realistic workloads and benchmarking capabilities.
"""

try:
    # Try relative imports first (when imported as a package)
    from .workloads import (
        Workload,
        WorkloadPattern,
        Operation,
        StandardWorkloads,
        create_custom_workload
    )
    from .benchmark_runner import BenchmarkRunner
except ImportError:
    # Fall back to absolute imports (when run directly)
    from benchmarking.workloads import (
        Workload,
        WorkloadPattern,
        Operation,
        StandardWorkloads,
        create_custom_workload
    )
    from benchmarking.benchmark_runner import BenchmarkRunner

__all__ = [
    'Workload',
    'WorkloadPattern',
    'Operation',
    'StandardWorkloads',
    'create_custom_workload',
    'BenchmarkRunner'
]