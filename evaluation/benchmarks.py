"""Custom MCP-specific benchmarks beyond SWE-bench."""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

from ..core import MCPServerWrapper
from ..sandbox import SandboxManager


logger = logging.getLogger(__name__)


class BenchmarkType(str, Enum):
    """Types of MCP benchmarks."""
    
    MULTI_TOOL_COORDINATION = "multi_tool_coordination"
    LONG_RUNNING_OPERATIONS = "long_running_operations"
    CONCURRENT_REQUESTS = "concurrent_requests"
    ERROR_RECOVERY = "error_recovery"
    RESOURCE_MANAGEMENT = "resource_management"
    STATE_CONSISTENCY = "state_consistency"
    TOOL_CHAINING = "tool_chaining"
    CONTEXT_SWITCHING = "context_switching"


@dataclass
class BenchmarkTask:
    """Represents a custom benchmark task."""
    
    id: str
    name: str
    type: BenchmarkType
    description: str
    
    # Task specification
    tools_required: List[str] = field(default_factory=list)
    expected_behavior: Dict[str, Any] = field(default_factory=dict)
    success_criteria: Dict[str, Any] = field(default_factory=dict)
    
    # Configuration
    timeout: int = 300
    max_iterations: int = 10
    parallel_operations: int = 1
    
    # Test data
    test_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "tools_required": self.tools_required,
            "timeout": self.timeout,
            "test_data": self.test_data
        }


@dataclass
class BenchmarkResult:
    """Result of a benchmark execution."""
    
    task_id: str
    success: bool
    execution_time: float
    
    # Performance metrics
    operations_completed: int = 0
    operations_failed: int = 0
    average_operation_time: float = 0.0
    
    # Tool usage
    tools_used: List[str] = field(default_factory=list)
    tool_calls: int = 0
    tool_errors: int = 0
    
    # Concurrency metrics
    max_concurrent_operations: int = 0
    concurrency_errors: int = 0
    
    # Resource metrics
    peak_memory_mb: float = 0.0
    average_cpu_percent: float = 0.0
    
    # Validation
    criteria_met: Dict[str, bool] = field(default_factory=dict)
    validation_errors: List[str] = field(default_factory=list)
    
    # Detailed results
    operation_results: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "success": self.success,
            "execution_time": self.execution_time,
            "operations_completed": self.operations_completed,
            "operations_failed": self.operations_failed,
            "average_operation_time": self.average_operation_time,
            "tools_used": self.tools_used,
            "tool_calls": self.tool_calls,
            "tool_errors": self.tool_errors,
            "max_concurrent_operations": self.max_concurrent_operations,
            "peak_memory_mb": self.peak_memory_mb,
            "average_cpu_percent": self.average_cpu_percent,
            "criteria_met": self.criteria_met
        }
    
    @property
    def success_rate(self) -> float:
        """Calculate operation success rate."""
        total = self.operations_completed + self.operations_failed
        if total == 0:
            return 0.0
        return self.operations_completed / total


class MCPBenchmark:
    """Base class for MCP-specific benchmarks."""
    
    def __init__(
        self,
        mcp_wrapper: MCPServerWrapper,
        sandbox_manager: Optional[SandboxManager] = None
    ):
        self.mcp_wrapper = mcp_wrapper
        self.sandbox_manager = sandbox_manager
        
    async def run_task(
        self,
        task: BenchmarkTask,
        progress_callback: Optional[Callable] = None
    ) -> BenchmarkResult:
        """Run a single benchmark task."""
        
        logger.info(f"Running benchmark task: {task.name}")
        start_time = time.time()
        
        result = BenchmarkResult(
            task_id=task.id,
            success=False,
            execution_time=0.0
        )
        
        try:
            # Select appropriate benchmark implementation
            if task.type == BenchmarkType.MULTI_TOOL_COORDINATION:
                await self._run_multi_tool_coordination(task, result)
            elif task.type == BenchmarkType.LONG_RUNNING_OPERATIONS:
                await self._run_long_running_operations(task, result)
            elif task.type == BenchmarkType.CONCURRENT_REQUESTS:
                await self._run_concurrent_requests(task, result)
            elif task.type == BenchmarkType.ERROR_RECOVERY:
                await self._run_error_recovery(task, result)
            elif task.type == BenchmarkType.RESOURCE_MANAGEMENT:
                await self._run_resource_management(task, result)
            elif task.type == BenchmarkType.STATE_CONSISTENCY:
                await self._run_state_consistency(task, result)
            elif task.type == BenchmarkType.TOOL_CHAINING:
                await self._run_tool_chaining(task, result)
            elif task.type == BenchmarkType.CONTEXT_SWITCHING:
                await self._run_context_switching(task, result)
            else:
                raise ValueError(f"Unknown benchmark type: {task.type}")
            
            # Validate results
            result.success = self._validate_results(task, result)
            
        except asyncio.TimeoutError:
            result.validation_errors.append(f"Task timed out after {task.timeout}s")
            
        except Exception as e:
            result.validation_errors.append(str(e))
            logger.error(f"Benchmark task {task.id} failed: {e}")
            
        finally:
            result.execution_time = time.time() - start_time
            
            if progress_callback:
                progress_callback(task, result)
        
        return result
    
    async def _run_multi_tool_coordination(
        self,
        task: BenchmarkTask,
        result: BenchmarkResult
    ) -> None:
        """Test coordination between multiple MCP tools."""
        
        # Example: File operations coordinated with git operations
        operations = [
            ("create_file", {"path": "/tmp/test1.txt", "content": "Test 1"}),
            ("create_file", {"path": "/tmp/test2.txt", "content": "Test 2"}),
            ("git_init", {"directory": "/tmp"}),
            ("git_add", {"files": ["test1.txt", "test2.txt"]}),
            ("git_commit", {"message": "Initial commit"}),
            ("edit_file", {"path": "/tmp/test1.txt", "content": "Modified"}),
            ("git_diff", {}),
            ("git_commit", {"message": "Update test1"}),
            ("git_log", {"limit": 5})
        ]
        
        for tool, params in operations:
            start = time.time()
            
            try:
                response = await self.mcp_wrapper.call_tool(tool, params)
                
                result.operations_completed += 1
                result.tools_used.append(tool)
                result.tool_calls += 1
                
                result.operation_results.append({
                    "tool": tool,
                    "success": True,
                    "duration": time.time() - start,
                    "response": response
                })
                
            except Exception as e:
                result.operations_failed += 1
                result.tool_errors += 1
                
                result.operation_results.append({
                    "tool": tool,
                    "success": False,
                    "error": str(e),
                    "duration": time.time() - start
                })
    
    async def _run_long_running_operations(
        self,
        task: BenchmarkTask,
        result: BenchmarkResult
    ) -> None:
        """Test handling of long-running operations."""
        
        # Test operations that take significant time
        long_operations = [
            ("download_large_file", {
                "url": "https://example.com/large_file.zip",
                "size_mb": 100
            }),
            ("process_data", {
                "input_file": "/tmp/data.csv",
                "operations": ["sort", "filter", "aggregate"],
                "rows": 1000000
            }),
            ("train_model", {
                "dataset": "/tmp/training_data",
                "epochs": 10,
                "batch_size": 32
            })
        ]
        
        tasks = []
        for op_name, params in long_operations:
            # Simulate long-running operation
            async def long_op(name, p):
                start = time.time()
                try:
                    # Add timeout handling
                    response = await asyncio.wait_for(
                        self.mcp_wrapper.call_tool(name, p),
                        timeout=60
                    )
                    
                    return {
                        "operation": name,
                        "success": True,
                        "duration": time.time() - start,
                        "response": response
                    }
                except asyncio.TimeoutError:
                    return {
                        "operation": name,
                        "success": False,
                        "error": "Operation timed out",
                        "duration": time.time() - start
                    }
                except Exception as e:
                    return {
                        "operation": name,
                        "success": False,
                        "error": str(e),
                        "duration": time.time() - start
                    }
            
            tasks.append(long_op(op_name, params))
        
        # Run operations
        results = await asyncio.gather(*tasks)
        
        for op_result in results:
            if op_result["success"]:
                result.operations_completed += 1
            else:
                result.operations_failed += 1
            
            result.operation_results.append(op_result)
            result.tool_calls += 1
    
    async def _run_concurrent_requests(
        self,
        task: BenchmarkTask,
        result: BenchmarkResult
    ) -> None:
        """Test handling of concurrent MCP requests."""
        
        concurrency_levels = [1, 5, 10, 20, 50]
        
        for level in concurrency_levels:
            # Create concurrent operations
            operations = []
            for i in range(level):
                operations.append(
                    self.mcp_wrapper.call_tool(
                        "echo",
                        {"message": f"Concurrent request {i}"}
                    )
                )
            
            # Measure concurrent execution
            start = time.time()
            
            try:
                responses = await asyncio.gather(*operations, return_exceptions=True)
                duration = time.time() - start
                
                successful = sum(1 for r in responses if not isinstance(r, Exception))
                failed = len(responses) - successful
                
                result.operations_completed += successful
                result.operations_failed += failed
                result.max_concurrent_operations = max(
                    result.max_concurrent_operations,
                    level
                )
                
                result.operation_results.append({
                    "concurrency_level": level,
                    "successful": successful,
                    "failed": failed,
                    "duration": duration,
                    "throughput": successful / duration if duration > 0 else 0
                })
                
            except Exception as e:
                result.concurrency_errors += 1
                result.validation_errors.append(
                    f"Concurrency test failed at level {level}: {e}"
                )
    
    async def _run_error_recovery(
        self,
        task: BenchmarkTask,
        result: BenchmarkResult
    ) -> None:
        """Test error recovery capabilities."""
        
        # Test various error scenarios
        error_scenarios = [
            # Invalid parameters
            ("read_file", {"path": None}),
            
            # Non-existent resources
            ("read_file", {"path": "/nonexistent/file.txt"}),
            
            # Permission errors
            ("write_file", {"path": "/root/protected.txt", "content": "test"}),
            
            # Malformed input
            ("parse_json", {"content": "{invalid json}"}),
            
            # Resource exhaustion
            ("allocate_memory", {"size_gb": 1000}),
        ]
        
        for tool, params in error_scenarios:
            try:
                # Attempt operation that should fail
                await self.mcp_wrapper.call_tool(tool, params)
                
                # If it didn't fail, that's unexpected
                result.validation_errors.append(
                    f"Expected error for {tool} but succeeded"
                )
                
            except Exception as e:
                # Error was expected, now test recovery
                result.tool_errors += 1
                
                # Try recovery operation
                recovery_success = await self._attempt_recovery(tool, params)
                
                if recovery_success:
                    result.operations_completed += 1
                else:
                    result.operations_failed += 1
                
                result.operation_results.append({
                    "scenario": f"{tool}_error",
                    "error": str(e),
                    "recovery_attempted": True,
                    "recovery_successful": recovery_success
                })
    
    async def _run_resource_management(
        self,
        task: BenchmarkTask,
        result: BenchmarkResult
    ) -> None:
        """Test resource management and cleanup."""
        
        # Track resource usage over time
        resource_samples = []
        
        # Create resources
        created_resources = []
        for i in range(10):
            # Create temporary file
            file_path = f"/tmp/resource_test_{i}.txt"
            await self.mcp_wrapper.call_tool(
                "write_file",
                {"path": file_path, "content": f"Resource {i}"}
            )
            created_resources.append(file_path)
            
            # Sample resource usage
            if self.sandbox_manager:
                metrics = await self._get_resource_metrics()
                resource_samples.append(metrics)
        
        # Use resources
        for resource in created_resources:
            await self.mcp_wrapper.call_tool(
                "read_file",
                {"path": resource}
            )
        
        # Clean up resources
        for resource in created_resources:
            await self.mcp_wrapper.call_tool(
                "delete_file",
                {"path": resource}
            )
        
        # Verify cleanup
        for resource in created_resources:
            try:
                await self.mcp_wrapper.call_tool(
                    "read_file",
                    {"path": resource}
                )
                result.validation_errors.append(
                    f"Resource not cleaned up: {resource}"
                )
            except:
                # Resource was properly cleaned up
                pass
        
        # Calculate resource metrics
        if resource_samples:
            result.peak_memory_mb = max(s.get("memory_mb", 0) for s in resource_samples)
            result.average_cpu_percent = sum(s.get("cpu_percent", 0) for s in resource_samples) / len(resource_samples)
        
        result.operations_completed = len(created_resources)
    
    async def _run_state_consistency(
        self,
        task: BenchmarkTask,
        result: BenchmarkResult
    ) -> None:
        """Test state consistency across operations."""
        
        # Initialize state
        initial_state = {
            "counter": 0,
            "items": [],
            "flags": {}
        }
        
        await self.mcp_wrapper.call_tool(
            "set_state",
            {"state": initial_state}
        )
        
        # Perform concurrent state modifications
        async def modify_state(operation_id):
            # Increment counter
            await self.mcp_wrapper.call_tool(
                "increment_counter",
                {"amount": 1}
            )
            
            # Add item
            await self.mcp_wrapper.call_tool(
                "add_item",
                {"item": f"item_{operation_id}"}
            )
            
            # Set flag
            await self.mcp_wrapper.call_tool(
                "set_flag",
                {"key": f"flag_{operation_id}", "value": True}
            )
        
        # Run concurrent modifications
        tasks = [modify_state(i) for i in range(10)]
        await asyncio.gather(*tasks)
        
        # Verify final state
        final_state = await self.mcp_wrapper.call_tool("get_state", {})
        
        # Check consistency
        expected_counter = 10
        expected_items = 10
        expected_flags = 10
        
        if final_state.get("counter") != expected_counter:
            result.validation_errors.append(
                f"Counter inconsistent: expected {expected_counter}, got {final_state.get('counter')}"
            )
        
        if len(final_state.get("items", [])) != expected_items:
            result.validation_errors.append(
                f"Items inconsistent: expected {expected_items}, got {len(final_state.get('items', []))}"
            )
        
        if len(final_state.get("flags", {})) != expected_flags:
            result.validation_errors.append(
                f"Flags inconsistent: expected {expected_flags}, got {len(final_state.get('flags', {}))}"
            )
        
        result.operations_completed = 30  # 3 operations per modification * 10
    
    async def _run_tool_chaining(
        self,
        task: BenchmarkTask,
        result: BenchmarkResult
    ) -> None:
        """Test chaining of multiple tools."""
        
        # Define tool chain
        chain = [
            ("fetch_data", {"url": "https://api.example.com/data"}),
            ("parse_json", {"use_previous_result": True}),
            ("filter_data", {"field": "status", "value": "active"}),
            ("transform_data", {"operation": "normalize"}),
            ("save_data", {"path": "/tmp/processed_data.json"})
        ]
        
        previous_result = None
        
        for tool, params in chain:
            # Add previous result if needed
            if params.get("use_previous_result") and previous_result:
                params["data"] = previous_result
            
            try:
                response = await self.mcp_wrapper.call_tool(tool, params)
                previous_result = response.get("result")
                
                result.operations_completed += 1
                result.tools_used.append(tool)
                
                result.operation_results.append({
                    "tool": tool,
                    "success": True,
                    "has_output": previous_result is not None
                })
                
            except Exception as e:
                result.operations_failed += 1
                result.validation_errors.append(
                    f"Chain broken at {tool}: {e}"
                )
                break
    
    async def _run_context_switching(
        self,
        task: BenchmarkTask,
        result: BenchmarkResult
    ) -> None:
        """Test context switching between different tasks."""
        
        # Create multiple contexts
        contexts = []
        for i in range(3):
            context_id = await self.mcp_wrapper.call_tool(
                "create_context",
                {"name": f"context_{i}"}
            )
            contexts.append(context_id)
        
        # Switch between contexts and perform operations
        for round in range(5):
            for context_id in contexts:
                # Switch context
                await self.mcp_wrapper.call_tool(
                    "switch_context",
                    {"context_id": context_id}
                )
                
                # Perform context-specific operation
                await self.mcp_wrapper.call_tool(
                    "append_log",
                    {"message": f"Round {round} in context {context_id}"}
                )
                
                result.operations_completed += 1
        
        # Verify context isolation
        for context_id in contexts:
            await self.mcp_wrapper.call_tool(
                "switch_context",
                {"context_id": context_id}
            )
            
            logs = await self.mcp_wrapper.call_tool(
                "get_logs",
                {}
            )
            
            # Should have exactly 5 logs per context
            if len(logs) != 5:
                result.validation_errors.append(
                    f"Context {context_id} has {len(logs)} logs, expected 5"
                )
    
    async def _attempt_recovery(
        self,
        tool: str,
        failed_params: Dict[str, Any]
    ) -> bool:
        """Attempt to recover from a failed operation."""
        
        # Simple recovery strategies
        recovery_strategies = {
            "read_file": lambda: self.mcp_wrapper.call_tool(
                "create_file",
                {"path": failed_params.get("path", "/tmp/recovery.txt"), "content": ""}
            ),
            "write_file": lambda: self.mcp_wrapper.call_tool(
                "create_directory",
                {"path": Path(failed_params.get("path", "/tmp/test")).parent}
            ),
            "parse_json": lambda: self.mcp_wrapper.call_tool(
                "validate_json",
                {"content": failed_params.get("content", "{}")}
            )
        }
        
        strategy = recovery_strategies.get(tool)
        if strategy:
            try:
                await strategy()
                return True
            except:
                return False
        
        return False
    
    async def _get_resource_metrics(self) -> Dict[str, float]:
        """Get current resource usage metrics."""
        
        # Simplified metrics collection
        import psutil
        
        return {
            "memory_mb": psutil.virtual_memory().used / (1024 * 1024),
            "cpu_percent": psutil.cpu_percent(interval=0.1)
        }
    
    def _validate_results(
        self,
        task: BenchmarkTask,
        result: BenchmarkResult
    ) -> bool:
        """Validate benchmark results against success criteria."""
        
        # Check each criterion
        for criterion, expected in task.success_criteria.items():
            if criterion == "min_success_rate":
                actual = result.success_rate
                met = actual >= expected
            elif criterion == "max_execution_time":
                actual = result.execution_time
                met = actual <= expected
            elif criterion == "min_operations":
                actual = result.operations_completed
                met = actual >= expected
            elif criterion == "max_errors":
                actual = result.operations_failed + result.tool_errors
                met = actual <= expected
            else:
                met = True
            
            result.criteria_met[criterion] = met
        
        # All criteria must be met
        return all(result.criteria_met.values())


class CustomBenchmark(MCPBenchmark):
    """Custom benchmark implementation for specific test scenarios."""
    
    def __init__(
        self,
        mcp_wrapper: MCPServerWrapper,
        test_definition: Dict[str, Any]
    ):
        super().__init__(mcp_wrapper)
        self.test_definition = test_definition
        
    async def run(self) -> BenchmarkResult:
        """Run custom benchmark."""
        
        # Create task from definition
        task = BenchmarkTask(
            id=self.test_definition.get("id", "custom"),
            name=self.test_definition.get("name", "Custom Test"),
            type=BenchmarkType(self.test_definition.get("type", "multi_tool_coordination")),
            description=self.test_definition.get("description", ""),
            tools_required=self.test_definition.get("tools", []),
            expected_behavior=self.test_definition.get("expected", {}),
            success_criteria=self.test_definition.get("criteria", {}),
            test_data=self.test_definition.get("data", {})
        )
        
        return await self.run_task(task)


class BenchmarkSuite:
    """Collection of benchmarks to run together."""
    
    def __init__(self, name: str = "MCP Benchmark Suite"):
        self.name = name
        self.benchmarks: List[BenchmarkTask] = []
        self._create_standard_benchmarks()
        
    def _create_standard_benchmarks(self):
        """Create standard MCP benchmark tasks."""
        
        self.benchmarks = [
            BenchmarkTask(
                id="multi_tool_1",
                name="Basic Multi-Tool Coordination",
                type=BenchmarkType.MULTI_TOOL_COORDINATION,
                description="Test basic coordination between file and git tools",
                tools_required=["create_file", "git_init", "git_commit"],
                success_criteria={
                    "min_success_rate": 0.9,
                    "max_execution_time": 30
                }
            ),
            BenchmarkTask(
                id="concurrent_1",
                name="Concurrent Request Handling",
                type=BenchmarkType.CONCURRENT_REQUESTS,
                description="Test handling of concurrent MCP requests",
                tools_required=["echo"],
                success_criteria={
                    "min_operations": 50,
                    "max_errors": 5
                },
                parallel_operations=20
            ),
            BenchmarkTask(
                id="long_running_1",
                name="Long Running Operations",
                type=BenchmarkType.LONG_RUNNING_OPERATIONS,
                description="Test handling of operations that take significant time",
                tools_required=["process_data", "download_file"],
                success_criteria={
                    "min_success_rate": 0.8,
                    "max_execution_time": 300
                },
                timeout=600
            ),
            BenchmarkTask(
                id="error_recovery_1",
                name="Error Recovery",
                type=BenchmarkType.ERROR_RECOVERY,
                description="Test error handling and recovery capabilities",
                tools_required=["read_file", "write_file"],
                success_criteria={
                    "min_success_rate": 0.7,
                    "max_errors": 10
                }
            ),
            BenchmarkTask(
                id="state_consistency_1",
                name="State Consistency",
                type=BenchmarkType.STATE_CONSISTENCY,
                description="Test state consistency under concurrent modifications",
                tools_required=["set_state", "get_state", "increment_counter"],
                success_criteria={
                    "min_success_rate": 1.0,  # Must be perfectly consistent
                    "max_errors": 0
                }
            ),
            BenchmarkTask(
                id="resource_mgmt_1",
                name="Resource Management",
                type=BenchmarkType.RESOURCE_MANAGEMENT,
                description="Test resource allocation and cleanup",
                tools_required=["write_file", "delete_file"],
                success_criteria={
                    "min_operations": 10,
                    "max_errors": 0
                }
            ),
            BenchmarkTask(
                id="tool_chain_1",
                name="Tool Chaining",
                type=BenchmarkType.TOOL_CHAINING,
                description="Test chaining multiple tools together",
                tools_required=["fetch_data", "parse_json", "save_data"],
                success_criteria={
                    "min_success_rate": 0.9,
                    "max_execution_time": 60
                }
            ),
            BenchmarkTask(
                id="context_switch_1",
                name="Context Switching",
                type=BenchmarkType.CONTEXT_SWITCHING,
                description="Test context switching between different tasks",
                tools_required=["create_context", "switch_context"],
                success_criteria={
                    "min_operations": 15,
                    "max_errors": 0
                }
            )
        ]
    
    def add_benchmark(self, task: BenchmarkTask):
        """Add a benchmark to the suite."""
        self.benchmarks.append(task)
    
    def get_benchmarks(
        self,
        types: Optional[List[BenchmarkType]] = None
    ) -> List[BenchmarkTask]:
        """Get benchmarks filtered by type."""
        
        if not types:
            return self.benchmarks
        
        return [b for b in self.benchmarks if b.type in types]
    
    async def run_suite(
        self,
        mcp_wrapper: MCPServerWrapper,
        parallel: int = 1,
        types: Optional[List[BenchmarkType]] = None
    ) -> List[BenchmarkResult]:
        """Run all benchmarks in the suite."""
        
        benchmarks_to_run = self.get_benchmarks(types)
        runner = MCPBenchmark(mcp_wrapper)
        
        if parallel == 1:
            # Sequential execution
            results = []
            for task in benchmarks_to_run:
                result = await runner.run_task(task)
                results.append(result)
                logger.info(f"Completed {len(results)}/{len(benchmarks_to_run)} benchmarks")
            
            return results
        
        # Parallel execution
        semaphore = asyncio.Semaphore(parallel)
        
        async def run_with_limit(task):
            async with semaphore:
                return await runner.run_task(task)
        
        tasks = [run_with_limit(task) for task in benchmarks_to_run]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Create error result
                error_result = BenchmarkResult(
                    task_id=benchmarks_to_run[i].id,
                    success=False,
                    execution_time=0.0
                )
                error_result.validation_errors.append(str(result))
                processed_results.append(error_result)
            else:
                processed_results.append(result)
        
        return processed_results
    
    def generate_report(self, results: List[BenchmarkResult]) -> Dict[str, Any]:
        """Generate a report from benchmark results."""
        
        total = len(results)
        successful = sum(1 for r in results if r.success)
        
        # Group by type
        by_type = {}
        for task, result in zip(self.benchmarks, results):
            type_name = task.type.value
            if type_name not in by_type:
                by_type[type_name] = {
                    "total": 0,
                    "successful": 0,
                    "average_time": 0,
                    "results": []
                }
            
            by_type[type_name]["total"] += 1
            if result.success:
                by_type[type_name]["successful"] += 1
            by_type[type_name]["results"].append(result)
        
        # Calculate averages
        for type_data in by_type.values():
            times = [r.execution_time for r in type_data["results"]]
            type_data["average_time"] = sum(times) / len(times) if times else 0
            del type_data["results"]  # Remove detailed results from summary
        
        return {
            "suite_name": self.name,
            "total_benchmarks": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": successful / total if total > 0 else 0,
            "by_type": by_type,
            "execution_time": sum(r.execution_time for r in results),
            "timestamp": datetime.now().isoformat()
        }