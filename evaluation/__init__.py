"""SWE-bench evaluation framework for MCP agents."""

from .swe_bench import (
    SWEBenchAdapter,
    SWEBenchDataset,
    SWEBenchTask,
    SWEBenchResult,
    DatasetType
)
from .pipeline import (
    TaskExecutionPipeline,
    ExecutionConfig,
    ExecutionResult,
    PipelineStage
)
from .benchmarks import (
    MCPBenchmark,
    CustomBenchmark,
    BenchmarkSuite,
    BenchmarkResult
)
from .metrics import (
    PerformanceMetrics,
    MetricsCollector,
    MetricsReport,
    evaluate_agent
)

__all__ = [
    # SWE-bench
    "SWEBenchAdapter",
    "SWEBenchDataset",
    "SWEBenchTask",
    "SWEBenchResult",
    "DatasetType",
    
    # Pipeline
    "TaskExecutionPipeline",
    "ExecutionConfig",
    "ExecutionResult",
    "PipelineStage",
    
    # Benchmarks
    "MCPBenchmark",
    "CustomBenchmark",
    "BenchmarkSuite",
    "BenchmarkResult",
    
    # Metrics
    "PerformanceMetrics",
    "MetricsCollector",
    "MetricsReport",
    "evaluate_agent"
]