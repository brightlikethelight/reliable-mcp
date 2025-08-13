"""Performance metrics collection and analysis for MCP agent evaluation."""

import time
import json
import statistics
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import logging

import numpy as np
from opentelemetry import metrics

from .swe_bench import SWEBenchResult
from .benchmarks import BenchmarkResult
from .pipeline import ExecutionResult


logger = logging.getLogger(__name__)
meter = metrics.get_meter(__name__)

# OpenTelemetry metrics
task_completion_rate = meter.create_observable_gauge(
    "evaluation.task_completion_rate",
    callbacks=[],
    description="Rate of successful task completions"
)
average_time_to_solution = meter.create_observable_gauge(
    "evaluation.average_time_to_solution",
    callbacks=[],
    description="Average time to solve tasks",
    unit="s"
)
resource_utilization = meter.create_histogram(
    "evaluation.resource_utilization",
    description="Resource utilization during evaluation",
    unit="percent"
)


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics for agent evaluation."""
    
    # Task completion metrics
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    timeout_tasks: int = 0
    
    # Time metrics
    total_execution_time: float = 0.0
    average_time_per_task: float = 0.0
    median_time_per_task: float = 0.0
    min_time_per_task: float = float('inf')
    max_time_per_task: float = 0.0
    
    # Resource metrics
    average_cpu_usage: float = 0.0
    peak_cpu_usage: float = 0.0
    average_memory_mb: float = 0.0
    peak_memory_mb: float = 0.0
    total_tokens_used: int = 0
    
    # Tool usage metrics
    total_tool_calls: int = 0
    unique_tools_used: int = 0
    average_tools_per_task: float = 0.0
    tool_error_rate: float = 0.0
    
    # Quality metrics
    test_pass_rate: float = 0.0
    patch_application_rate: float = 0.0
    validation_success_rate: float = 0.0
    
    # Efficiency metrics
    throughput: float = 0.0  # Tasks per hour
    efficiency_score: float = 0.0  # Combined metric
    
    # Detailed breakdowns
    time_distribution: List[float] = field(default_factory=list)
    resource_samples: List[Dict[str, float]] = field(default_factory=list)
    tool_usage_distribution: Dict[str, int] = field(default_factory=dict)
    error_categories: Dict[str, int] = field(default_factory=dict)
    
    def calculate_derived_metrics(self):
        """Calculate derived metrics from raw data."""
        
        if self.total_tasks > 0:
            self.completion_rate = self.completed_tasks / self.total_tasks
            
            if self.time_distribution:
                self.average_time_per_task = statistics.mean(self.time_distribution)
                self.median_time_per_task = statistics.median(self.time_distribution)
                self.min_time_per_task = min(self.time_distribution)
                self.max_time_per_task = max(self.time_distribution)
            
            if self.total_execution_time > 0:
                self.throughput = (self.completed_tasks / self.total_execution_time) * 3600
            
            # Calculate efficiency score (0-100)
            self.efficiency_score = self._calculate_efficiency_score()
    
    def _calculate_efficiency_score(self) -> float:
        """Calculate overall efficiency score."""
        
        scores = []
        
        # Completion rate (40% weight)
        if self.total_tasks > 0:
            completion_score = (self.completed_tasks / self.total_tasks) * 40
            scores.append(completion_score)
        
        # Time efficiency (30% weight)
        if self.average_time_per_task > 0:
            # Assume 300s is baseline good time
            time_score = min(30, (300 / self.average_time_per_task) * 30)
            scores.append(time_score)
        
        # Resource efficiency (20% weight)
        if self.average_cpu_usage > 0:
            # Lower CPU usage is better
            resource_score = (1 - self.average_cpu_usage / 100) * 20
            scores.append(resource_score)
        
        # Quality (10% weight)
        if self.test_pass_rate > 0:
            quality_score = self.test_pass_rate * 10
            scores.append(quality_score)
        
        return sum(scores) if scores else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "task_metrics": {
                "total": self.total_tasks,
                "completed": self.completed_tasks,
                "failed": self.failed_tasks,
                "timeout": self.timeout_tasks,
                "completion_rate": self.completed_tasks / max(self.total_tasks, 1)
            },
            "time_metrics": {
                "total_time": self.total_execution_time,
                "average": self.average_time_per_task,
                "median": self.median_time_per_task,
                "min": self.min_time_per_task,
                "max": self.max_time_per_task
            },
            "resource_metrics": {
                "average_cpu": self.average_cpu_usage,
                "peak_cpu": self.peak_cpu_usage,
                "average_memory_mb": self.average_memory_mb,
                "peak_memory_mb": self.peak_memory_mb,
                "total_tokens": self.total_tokens_used
            },
            "tool_metrics": {
                "total_calls": self.total_tool_calls,
                "unique_tools": self.unique_tools_used,
                "average_per_task": self.average_tools_per_task,
                "error_rate": self.tool_error_rate
            },
            "quality_metrics": {
                "test_pass_rate": self.test_pass_rate,
                "patch_application_rate": self.patch_application_rate,
                "validation_success_rate": self.validation_success_rate
            },
            "efficiency": {
                "throughput": self.throughput,
                "efficiency_score": self.efficiency_score
            }
        }


class MetricsCollector:
    """Collects and aggregates metrics from various sources."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.home() / ".cache" / "mcp-metrics"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_metrics = PerformanceMetrics()
        self.historical_metrics: List[PerformanceMetrics] = []
        
    def collect_from_swe_bench(
        self,
        results: List[SWEBenchResult]
    ) -> PerformanceMetrics:
        """Collect metrics from SWE-bench results."""
        
        metrics = PerformanceMetrics()
        
        metrics.total_tasks = len(results)
        metrics.completed_tasks = sum(1 for r in results if r.success)
        metrics.failed_tasks = metrics.total_tasks - metrics.completed_tasks
        
        # Time metrics
        times = [r.execution_time for r in results]
        if times:
            metrics.time_distribution = times
            metrics.total_execution_time = sum(times)
        
        # Tool usage
        all_tools = []
        for result in results:
            all_tools.extend(result.tools_used)
            metrics.total_tool_calls += result.tool_calls_count
        
        if all_tools:
            tool_counts = defaultdict(int)
            for tool in all_tools:
                tool_counts[tool] += 1
            metrics.tool_usage_distribution = dict(tool_counts)
            metrics.unique_tools_used = len(tool_counts)
            metrics.average_tools_per_task = len(all_tools) / max(len(results), 1)
        
        # Resource metrics
        cpu_times = [r.cpu_time for r in results if r.cpu_time > 0]
        memory_peaks = [r.memory_peak_mb for r in results if r.memory_peak_mb > 0]
        
        if cpu_times:
            metrics.average_cpu_usage = statistics.mean(cpu_times)
            metrics.peak_cpu_usage = max(cpu_times)
        
        if memory_peaks:
            metrics.average_memory_mb = statistics.mean(memory_peaks)
            metrics.peak_memory_mb = max(memory_peaks)
        
        # Quality metrics
        test_pass_rates = [r.pass_rate for r in results]
        if test_pass_rates:
            metrics.test_pass_rate = statistics.mean(test_pass_rates)
        
        patch_applications = sum(1 for r in results if r.patch_applied)
        metrics.patch_application_rate = patch_applications / max(len(results), 1)
        
        # Error analysis
        for result in results:
            if result.error:
                error_type = self._categorize_error(result.error)
                metrics.error_categories[error_type] = metrics.error_categories.get(error_type, 0) + 1
        
        metrics.calculate_derived_metrics()
        
        return metrics
    
    def collect_from_benchmarks(
        self,
        results: List[BenchmarkResult]
    ) -> PerformanceMetrics:
        """Collect metrics from custom benchmark results."""
        
        metrics = PerformanceMetrics()
        
        metrics.total_tasks = len(results)
        metrics.completed_tasks = sum(1 for r in results if r.success)
        metrics.failed_tasks = metrics.total_tasks - metrics.completed_tasks
        
        # Time metrics
        times = [r.execution_time for r in results]
        if times:
            metrics.time_distribution = times
            metrics.total_execution_time = sum(times)
        
        # Operation metrics
        total_ops = sum(r.operations_completed + r.operations_failed for r in results)
        successful_ops = sum(r.operations_completed for r in results)
        
        if total_ops > 0:
            metrics.validation_success_rate = successful_ops / total_ops
        
        # Tool metrics
        for result in results:
            metrics.total_tool_calls += result.tool_calls
            metrics.tool_error_rate = result.tool_errors / max(result.tool_calls, 1)
            
            for tool in result.tools_used:
                metrics.tool_usage_distribution[tool] = metrics.tool_usage_distribution.get(tool, 0) + 1
        
        metrics.unique_tools_used = len(metrics.tool_usage_distribution)
        
        # Resource metrics
        cpu_percents = [r.average_cpu_percent for r in results if r.average_cpu_percent > 0]
        memory_peaks = [r.peak_memory_mb for r in results if r.peak_memory_mb > 0]
        
        if cpu_percents:
            metrics.average_cpu_usage = statistics.mean(cpu_percents)
            metrics.peak_cpu_usage = max(cpu_percents)
        
        if memory_peaks:
            metrics.average_memory_mb = statistics.mean(memory_peaks)
            metrics.peak_memory_mb = max(memory_peaks)
        
        metrics.calculate_derived_metrics()
        
        return metrics
    
    def collect_from_pipeline(
        self,
        results: List[ExecutionResult]
    ) -> PerformanceMetrics:
        """Collect metrics from pipeline execution results."""
        
        metrics = PerformanceMetrics()
        
        metrics.total_tasks = len(results)
        metrics.completed_tasks = sum(1 for r in results if r.success)
        metrics.failed_tasks = metrics.total_tasks - metrics.completed_tasks
        
        # Time metrics
        times = [r.total_duration for r in results]
        if times:
            metrics.time_distribution = times
            metrics.total_execution_time = sum(times)
        
        # Stage analysis
        stage_times = defaultdict(list)
        for result in results:
            for stage in result.stages:
                stage_times[stage.stage].append(stage.duration)
        
        # Tool and token metrics
        for result in results:
            metrics.total_tool_calls += len(result.tools_used)
            metrics.total_tokens_used += result.tokens_used
            
            for tool in result.tools_used:
                metrics.tool_usage_distribution[tool] = metrics.tool_usage_distribution.get(tool, 0) + 1
        
        metrics.unique_tools_used = len(metrics.tool_usage_distribution)
        
        # Resource metrics
        cpu_seconds = [r.cpu_seconds for r in results if r.cpu_seconds > 0]
        memory_peaks = [r.peak_memory_mb for r in results if r.peak_memory_mb > 0]
        
        if cpu_seconds:
            metrics.average_cpu_usage = statistics.mean(cpu_seconds)
            metrics.peak_cpu_usage = max(cpu_seconds)
        
        if memory_peaks:
            metrics.average_memory_mb = statistics.mean(memory_peaks)
            metrics.peak_memory_mb = max(memory_peaks)
        
        # Quality metrics
        validation_passed = sum(1 for r in results if r.validation_passed)
        metrics.validation_success_rate = validation_passed / max(len(results), 1)
        
        # Error analysis
        for result in results:
            if result.error:
                error_type = self._categorize_error(result.error)
                metrics.error_categories[error_type] = metrics.error_categories.get(error_type, 0) + 1
            
            if result.failed_stage:
                stage_name = result.failed_stage.value
                metrics.error_categories[f"stage_{stage_name}"] = metrics.error_categories.get(f"stage_{stage_name}", 0) + 1
        
        metrics.calculate_derived_metrics()
        
        return metrics
    
    def aggregate_metrics(
        self,
        metrics_list: List[PerformanceMetrics]
    ) -> PerformanceMetrics:
        """Aggregate multiple metrics into a single summary."""
        
        if not metrics_list:
            return PerformanceMetrics()
        
        aggregated = PerformanceMetrics()
        
        # Sum basic counts
        aggregated.total_tasks = sum(m.total_tasks for m in metrics_list)
        aggregated.completed_tasks = sum(m.completed_tasks for m in metrics_list)
        aggregated.failed_tasks = sum(m.failed_tasks for m in metrics_list)
        aggregated.timeout_tasks = sum(m.timeout_tasks for m in metrics_list)
        
        # Aggregate time metrics
        all_times = []
        for m in metrics_list:
            all_times.extend(m.time_distribution)
        
        if all_times:
            aggregated.time_distribution = all_times
            aggregated.total_execution_time = sum(all_times)
        
        # Average resource metrics
        cpu_values = [m.average_cpu_usage for m in metrics_list if m.average_cpu_usage > 0]
        memory_values = [m.average_memory_mb for m in metrics_list if m.average_memory_mb > 0]
        
        if cpu_values:
            aggregated.average_cpu_usage = statistics.mean(cpu_values)
            aggregated.peak_cpu_usage = max(m.peak_cpu_usage for m in metrics_list)
        
        if memory_values:
            aggregated.average_memory_mb = statistics.mean(memory_values)
            aggregated.peak_memory_mb = max(m.peak_memory_mb for m in metrics_list)
        
        # Sum tool metrics
        aggregated.total_tool_calls = sum(m.total_tool_calls for m in metrics_list)
        aggregated.total_tokens_used = sum(m.total_tokens_used for m in metrics_list)
        
        # Merge tool usage distribution
        for m in metrics_list:
            for tool, count in m.tool_usage_distribution.items():
                aggregated.tool_usage_distribution[tool] = aggregated.tool_usage_distribution.get(tool, 0) + count
        
        aggregated.unique_tools_used = len(aggregated.tool_usage_distribution)
        
        # Average quality metrics
        test_rates = [m.test_pass_rate for m in metrics_list if m.test_pass_rate > 0]
        if test_rates:
            aggregated.test_pass_rate = statistics.mean(test_rates)
        
        # Merge error categories
        for m in metrics_list:
            for error_type, count in m.error_categories.items():
                aggregated.error_categories[error_type] = aggregated.error_categories.get(error_type, 0) + count
        
        aggregated.calculate_derived_metrics()
        
        return aggregated
    
    def save_metrics(
        self,
        metrics: PerformanceMetrics,
        name: str = "metrics"
    ):
        """Save metrics to cache."""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.cache_dir / f"{name}_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(metrics.to_dict(), f, indent=2)
        
        logger.info(f"Saved metrics to {filename}")
    
    def load_metrics(
        self,
        name_pattern: str = "metrics_*.json"
    ) -> List[PerformanceMetrics]:
        """Load metrics from cache."""
        
        metrics_list = []
        
        for file_path in self.cache_dir.glob(name_pattern):
            with open(file_path, 'r') as f:
                data = json.load(f)
                
                # Reconstruct metrics object
                metrics = PerformanceMetrics()
                # Simplified - would need proper deserialization
                metrics_list.append(metrics)
        
        return metrics_list
    
    def _categorize_error(self, error_message: str) -> str:
        """Categorize error messages."""
        
        error_lower = error_message.lower()
        
        if "timeout" in error_lower:
            return "timeout"
        elif "memory" in error_lower:
            return "memory"
        elif "permission" in error_lower:
            return "permission"
        elif "connection" in error_lower:
            return "connection"
        elif "syntax" in error_lower:
            return "syntax"
        elif "import" in error_lower:
            return "import"
        elif "attribute" in error_lower:
            return "attribute"
        else:
            return "other"


class MetricsReport:
    """Generate comprehensive metrics reports."""
    
    def __init__(self, metrics: PerformanceMetrics):
        self.metrics = metrics
        
    def generate_summary(self) -> str:
        """Generate a text summary of metrics."""
        
        lines = [
            "=" * 60,
            "MCP Agent Evaluation Metrics Report",
            "=" * 60,
            "",
            f"Total Tasks: {self.metrics.total_tasks}",
            f"Completed: {self.metrics.completed_tasks} ({self.metrics.completed_tasks / max(self.metrics.total_tasks, 1):.1%})",
            f"Failed: {self.metrics.failed_tasks}",
            f"Timeouts: {self.metrics.timeout_tasks}",
            "",
            "Time Metrics:",
            f"  Total Time: {self.metrics.total_execution_time:.2f}s",
            f"  Average: {self.metrics.average_time_per_task:.2f}s",
            f"  Median: {self.metrics.median_time_per_task:.2f}s",
            f"  Min: {self.metrics.min_time_per_task:.2f}s",
            f"  Max: {self.metrics.max_time_per_task:.2f}s",
            "",
            "Resource Usage:",
            f"  Average CPU: {self.metrics.average_cpu_usage:.1f}%",
            f"  Peak CPU: {self.metrics.peak_cpu_usage:.1f}%",
            f"  Average Memory: {self.metrics.average_memory_mb:.1f} MB",
            f"  Peak Memory: {self.metrics.peak_memory_mb:.1f} MB",
            f"  Total Tokens: {self.metrics.total_tokens_used:,}",
            "",
            "Tool Usage:",
            f"  Total Calls: {self.metrics.total_tool_calls}",
            f"  Unique Tools: {self.metrics.unique_tools_used}",
            f"  Average per Task: {self.metrics.average_tools_per_task:.1f}",
            f"  Error Rate: {self.metrics.tool_error_rate:.1%}",
            "",
            "Quality Metrics:",
            f"  Test Pass Rate: {self.metrics.test_pass_rate:.1%}",
            f"  Patch Application Rate: {self.metrics.patch_application_rate:.1%}",
            f"  Validation Success: {self.metrics.validation_success_rate:.1%}",
            "",
            "Efficiency:",
            f"  Throughput: {self.metrics.throughput:.2f} tasks/hour",
            f"  Efficiency Score: {self.metrics.efficiency_score:.1f}/100",
            ""
        ]
        
        # Add top tools
        if self.metrics.tool_usage_distribution:
            lines.append("Top Tools Used:")
            sorted_tools = sorted(
                self.metrics.tool_usage_distribution.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            for tool, count in sorted_tools:
                lines.append(f"  {tool}: {count}")
            lines.append("")
        
        # Add error breakdown
        if self.metrics.error_categories:
            lines.append("Error Categories:")
            for error_type, count in self.metrics.error_categories.items():
                lines.append(f"  {error_type}: {count}")
            lines.append("")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def generate_json(self) -> str:
        """Generate JSON report."""
        return json.dumps(self.metrics.to_dict(), indent=2)
    
    def generate_html(self) -> str:
        """Generate HTML report with visualizations."""
        
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>MCP Agent Evaluation Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .metric-card {{ 
            background: #f5f5f5; 
            padding: 15px; 
            margin: 10px 0; 
            border-radius: 5px;
        }}
        .metric-value {{ 
            font-size: 24px; 
            font-weight: bold; 
            color: #2196F3;
        }}
        .metric-label {{ 
            color: #666; 
            margin-bottom: 5px;
        }}
        .progress-bar {{
            background: #ddd;
            height: 20px;
            border-radius: 10px;
            overflow: hidden;
        }}
        .progress-fill {{
            background: #4CAF50;
            height: 100%;
            transition: width 0.5s;
        }}
    </style>
</head>
<body>
    <h1>MCP Agent Evaluation Report</h1>
    
    <div class="metric-card">
        <div class="metric-label">Task Completion Rate</div>
        <div class="metric-value">{completion_rate:.1%}</div>
        <div class="progress-bar">
            <div class="progress-fill" style="width: {completion_rate_percent}%"></div>
        </div>
    </div>
    
    <div class="metric-card">
        <div class="metric-label">Efficiency Score</div>
        <div class="metric-value">{efficiency_score:.1f}/100</div>
        <div class="progress-bar">
            <div class="progress-fill" style="width: {efficiency_score}%"></div>
        </div>
    </div>
    
    <div class="metric-card">
        <div class="metric-label">Average Time per Task</div>
        <div class="metric-value">{avg_time:.2f}s</div>
    </div>
    
    <div class="metric-card">
        <div class="metric-label">Throughput</div>
        <div class="metric-value">{throughput:.2f} tasks/hour</div>
    </div>
    
    <h2>Detailed Metrics</h2>
    <pre>{detailed_json}</pre>
</body>
</html>
"""
        
        completion_rate = self.metrics.completed_tasks / max(self.metrics.total_tasks, 1)
        
        return html_template.format(
            completion_rate=completion_rate,
            completion_rate_percent=completion_rate * 100,
            efficiency_score=self.metrics.efficiency_score,
            avg_time=self.metrics.average_time_per_task,
            throughput=self.metrics.throughput,
            detailed_json=json.dumps(self.metrics.to_dict(), indent=2)
        )


async def evaluate_agent(
    mcp_wrapper,
    test_suite: str = "swe_bench_lite",
    limit: Optional[int] = None
) -> Tuple[PerformanceMetrics, MetricsReport]:
    """Evaluate an MCP agent on a test suite."""
    
    from .swe_bench import SWEBenchAdapter, DatasetType
    from .benchmarks import BenchmarkSuite
    from ..sandbox import SandboxManager
    
    # Create components
    sandbox_manager = SandboxManager()
    collector = MetricsCollector()
    
    if test_suite.startswith("swe_bench"):
        # Run SWE-bench evaluation
        adapter = SWEBenchAdapter(mcp_wrapper, sandbox_manager)
        
        # Determine dataset type
        if "lite" in test_suite:
            dataset_type = DatasetType.LITE
        elif "verified" in test_suite:
            dataset_type = DatasetType.VERIFIED
        else:
            dataset_type = DatasetType.FULL
        
        # Load tasks
        tasks = await adapter.load_dataset(dataset_type)
        
        if limit:
            tasks = tasks[:limit]
        
        # Run evaluation
        results = await adapter.run_benchmark(tasks, parallel=4)
        
        # Collect metrics
        metrics = collector.collect_from_swe_bench(results)
        
    else:
        # Run custom benchmarks
        suite = BenchmarkSuite()
        
        results = await suite.run_suite(
            mcp_wrapper,
            parallel=4
        )
        
        # Collect metrics
        metrics = collector.collect_from_benchmarks(results)
    
    # Save metrics
    collector.save_metrics(metrics, test_suite)
    
    # Generate report
    report = MetricsReport(metrics)
    
    return metrics, report