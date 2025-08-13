#!/usr/bin/env python3
"""
SWE-bench Evaluation Demo for MCP Agents

This example demonstrates the comprehensive agent evaluation capabilities
using SWE-bench datasets and custom MCP benchmarks.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, List

from mcp_reliability_lab.evaluation import (
    SWEBenchAdapter, DatasetType, SWEBenchTask,
    TaskExecutionPipeline, ExecutionConfig,
    BenchmarkSuite, MCPBenchmark,
    MetricsCollector, MetricsReport, evaluate_agent
)
from mcp_reliability_lab.core import MCPServerWrapper
from mcp_reliability_lab.sandbox import SandboxManager
from mcp_reliability_lab.observability import setup_telemetry


async def swe_bench_basic_demo():
    """Demonstrate basic SWE-bench evaluation."""
    print("\n📚 SWE-bench Basic Evaluation Demo")
    print("=" * 50)
    
    # Create mock MCP wrapper for demo
    class MockMCPWrapper:
        async def call_tool(self, tool_name: str, params: Dict[str, Any]):
            # Simulate tool calls
            if tool_name == "solve_task":
                return {
                    "complete": True,
                    "patch": "diff --git a/file.py b/file.py\n+fixed",
                    "tools_used": ["read_file", "edit_file"],
                    "tokens": 1500
                }
            return {"result": f"Mock result for {tool_name}"}
        
        async def connect(self):
            pass
        
        async def disconnect(self):
            pass
    
    mcp_wrapper = MockMCPWrapper()
    sandbox_manager = SandboxManager()
    
    # Create SWE-bench adapter
    adapter = SWEBenchAdapter(mcp_wrapper, sandbox_manager)
    
    # Load dataset (will download and cache)
    print("Loading SWE-bench Lite dataset...")
    try:
        tasks = await adapter.load_dataset(DatasetType.LITE)
        print(f"✅ Loaded {len(tasks)} tasks from SWE-bench Lite")
        
        # Show first few tasks
        print("\nFirst 3 tasks:")
        for i, task in enumerate(tasks[:3]):
            print(f"\n{i+1}. {task.instance_id}")
            print(f"   Repository: {task.repo}")
            print(f"   Problem: {task.problem_statement[:100]}...")
            
    except Exception as e:
        print(f"ℹ️ Demo mode - using mock tasks: {e}")
        
        # Create mock tasks for demo
        tasks = [
            SWEBenchTask(
                instance_id="django__django-12345",
                repo="django/django",
                base_commit="abc123",
                problem_statement="Fix bug in QuerySet.filter() method",
                test_cmd="python -m pytest tests/",
                fail_to_pass=["test_queryset_filter"],
                pass_to_pass=["test_queryset_basic"]
            ),
            SWEBenchTask(
                instance_id="scikit-learn__scikit-learn-67890",
                repo="scikit-learn/scikit-learn",
                base_commit="def456",
                problem_statement="Improve accuracy of RandomForest classifier",
                test_cmd="pytest sklearn/tests/",
                fail_to_pass=["test_random_forest_accuracy"],
                pass_to_pass=["test_random_forest_basic"]
            )
        ]
    
    # Run evaluation on subset
    print("\n🚀 Running evaluation on 2 tasks...")
    results = []
    
    for task in tasks[:2]:
        print(f"\nEvaluating: {task.instance_id}")
        
        try:
            result = await adapter.run_task(task, use_cache=False)
            results.append(result)
            
            print(f"  Status: {'✅ Success' if result.success else '❌ Failed'}")
            print(f"  Execution Time: {result.execution_time:.2f}s")
            print(f"  Tools Used: {len(result.tools_used)}")
            print(f"  Tests Passed: {len(result.tests_passed)}")
            
        except Exception as e:
            print(f"  ℹ️ Demo error (expected): {e}")
    
    # Show statistics
    if results:
        stats = adapter.get_statistics(results)
        print(f"\n📊 Evaluation Statistics:")
        print(f"  Success Rate: {stats['success_rate']:.1%}")
        print(f"  Average Time: {stats['average_execution_time']:.2f}s")
        print(f"  Average Tool Calls: {stats['average_tool_calls']:.1f}")


async def task_pipeline_demo():
    """Demonstrate task execution pipeline."""
    print("\n⚙️ Task Execution Pipeline Demo")
    print("=" * 50)
    
    # Create mock components
    class MockMCPWrapper:
        async def call_tool(self, tool_name: str, params: Dict[str, Any]):
            return {"result": "success", "tools_used": ["test_tool"]}
    
    mcp_wrapper = MockMCPWrapper()
    sandbox_manager = SandboxManager()
    
    # Create pipeline with custom config
    config = ExecutionConfig(
        sandbox_template="swe_bench",
        agent_timeout=300,
        test_timeout=120,
        max_iterations=5,
        collect_artifacts=True
    )
    
    pipeline = TaskExecutionPipeline(mcp_wrapper, sandbox_manager, config)
    
    # Create a test task
    task = SWEBenchTask(
        instance_id="test-task-001",
        repo="test/repo",
        base_commit="main",
        problem_statement="Test problem for pipeline demo",
        test_cmd="pytest",
        fail_to_pass=["test_feature"],
        pass_to_pass=["test_basic"]
    )
    
    print("Pipeline Stages:")
    for stage in ["SETUP", "REPOSITORY_PREPARATION", "AGENT_INVOCATION", 
                  "PATCH_GENERATION", "PATCH_APPLICATION", "TEST_EXECUTION",
                  "VALIDATION", "CLEANUP"]:
        print(f"  - {stage}")
    
    print("\n🔄 Executing task through pipeline...")
    
    try:
        result = await pipeline.execute_task(task)
        
        print(f"\n📊 Pipeline Results:")
        print(f"  Task ID: {result.task_id}")
        print(f"  Success: {result.success}")
        print(f"  Duration: {result.total_duration:.2f}s")
        print(f"  Stages Completed: {len(result.stages)}")
        
        print("\n  Stage Breakdown:")
        for stage_result in result.stages:
            status = "✅" if stage_result.success else "❌"
            print(f"    {status} {stage_result.stage}: {stage_result.duration:.2f}s")
            
    except Exception as e:
        print(f"  ℹ️ Pipeline demo error (expected): {e}")


async def custom_benchmarks_demo():
    """Demonstrate custom MCP-specific benchmarks."""
    print("\n🎯 Custom MCP Benchmarks Demo")
    print("=" * 50)
    
    # Create mock MCP wrapper
    class MockMCPWrapper:
        async def call_tool(self, tool_name: str, params: Dict[str, Any]):
            await asyncio.sleep(0.01)  # Simulate latency
            return {"status": "success", "result": f"Result for {tool_name}"}
    
    mcp_wrapper = MockMCPWrapper()
    
    # Create benchmark suite
    suite = BenchmarkSuite("MCP Reliability Benchmarks")
    
    print(f"Benchmark Suite: {suite.name}")
    print(f"Total Benchmarks: {len(suite.benchmarks)}")
    
    print("\nBenchmark Types:")
    for benchmark in suite.benchmarks:
        print(f"  - {benchmark.name} ({benchmark.type.value})")
    
    # Run subset of benchmarks
    print("\n🚀 Running 3 benchmark tasks...")
    
    runner = MCPBenchmark(mcp_wrapper)
    results = []
    
    for task in suite.benchmarks[:3]:
        print(f"\nRunning: {task.name}")
        print(f"  Type: {task.type.value}")
        print(f"  Timeout: {task.timeout}s")
        
        try:
            result = await runner.run_task(task)
            results.append(result)
            
            print(f"  Status: {'✅ Success' if result.success else '❌ Failed'}")
            print(f"  Operations: {result.operations_completed}/{result.operations_completed + result.operations_failed}")
            print(f"  Success Rate: {result.success_rate:.1%}")
            print(f"  Execution Time: {result.execution_time:.2f}s")
            
        except Exception as e:
            print(f"  ℹ️ Benchmark error (expected in demo): {e}")
    
    # Generate report
    if results:
        report = suite.generate_report(results)
        print(f"\n📊 Benchmark Suite Report:")
        print(f"  Total Benchmarks: {report['total_benchmarks']}")
        print(f"  Successful: {report['successful']}")
        print(f"  Success Rate: {report['success_rate']:.1%}")
        print(f"  Total Time: {report['execution_time']:.2f}s")


async def performance_metrics_demo():
    """Demonstrate performance metrics collection and reporting."""
    print("\n📈 Performance Metrics Collection Demo")
    print("=" * 50)
    
    # Create metrics collector
    collector = MetricsCollector()
    
    # Simulate some results
    from mcp_reliability_lab.evaluation.swe_bench import SWEBenchResult
    from mcp_reliability_lab.evaluation.benchmarks import BenchmarkResult
    
    # Create mock SWE-bench results
    swe_results = [
        SWEBenchResult(
            task_id="task-1",
            success=True,
            execution_time=45.2,
            tests_passed=["test1", "test2"],
            tests_failed=["test3"],
            tools_used=["read_file", "edit_file", "run_command"],
            tool_calls_count=15,
            cpu_time=40.5,
            memory_peak_mb=512.3
        ),
        SWEBenchResult(
            task_id="task-2",
            success=False,
            execution_time=120.5,
            tests_passed=["test1"],
            tests_failed=["test2", "test3"],
            tools_used=["read_file", "write_file"],
            tool_calls_count=8,
            cpu_time=110.2,
            memory_peak_mb=768.9,
            error="Test execution failed"
        )
    ]
    
    # Collect metrics from SWE-bench
    swe_metrics = collector.collect_from_swe_bench(swe_results)
    
    print("SWE-bench Metrics:")
    print(f"  Completion Rate: {swe_metrics.completed_tasks}/{swe_metrics.total_tasks}")
    print(f"  Average Time: {swe_metrics.average_time_per_task:.2f}s")
    print(f"  Average CPU: {swe_metrics.average_cpu_usage:.1f}s")
    print(f"  Peak Memory: {swe_metrics.peak_memory_mb:.1f} MB")
    
    # Create mock benchmark results
    benchmark_results = [
        BenchmarkResult(
            task_id="bench-1",
            success=True,
            execution_time=30.5,
            operations_completed=10,
            operations_failed=2,
            tools_used=["tool1", "tool2", "tool3"],
            tool_calls=25,
            peak_memory_mb=256.7,
            average_cpu_percent=65.3
        )
    ]
    
    # Collect metrics from benchmarks
    bench_metrics = collector.collect_from_benchmarks(benchmark_results)
    
    print("\nBenchmark Metrics:")
    print(f"  Success Rate: {bench_metrics.validation_success_rate:.1%}")
    print(f"  Tool Calls: {bench_metrics.total_tool_calls}")
    print(f"  Average CPU: {bench_metrics.average_cpu_usage:.1f}%")
    
    # Aggregate all metrics
    all_metrics = collector.aggregate_metrics([swe_metrics, bench_metrics])
    
    print("\n📊 Aggregated Metrics:")
    print(f"  Total Tasks: {all_metrics.total_tasks}")
    print(f"  Completed: {all_metrics.completed_tasks}")
    print(f"  Total Time: {all_metrics.total_execution_time:.2f}s")
    print(f"  Efficiency Score: {all_metrics.efficiency_score:.1f}/100")
    
    # Generate report
    report = MetricsReport(all_metrics)
    
    print("\n" + "=" * 60)
    print(report.generate_summary())
    
    # Save metrics
    collector.save_metrics(all_metrics, "demo_metrics")
    print(f"\n💾 Metrics saved to cache")


async def comprehensive_evaluation_demo():
    """Demonstrate comprehensive agent evaluation."""
    print("\n🏆 Comprehensive Agent Evaluation Demo")
    print("=" * 50)
    
    # Create mock MCP wrapper
    class MockMCPAgent:
        async def call_tool(self, tool_name: str, params: Dict[str, Any]):
            # Simulate different behaviors
            import random
            
            if random.random() > 0.3:  # 70% success rate
                return {
                    "success": True,
                    "result": f"Completed {tool_name}",
                    "tools_used": ["tool1", "tool2"],
                    "patch": "mock patch" if tool_name == "solve_task" else None
                }
            else:
                raise Exception(f"Simulated failure in {tool_name}")
    
    mcp_agent = MockMCPAgent()
    
    print("Evaluation Configuration:")
    print("  Test Suite: SWE-bench Lite")
    print("  Task Limit: 5")
    print("  Parallel Execution: 2")
    
    print("\n🔄 Running comprehensive evaluation...")
    
    try:
        # Run evaluation
        metrics, report = await evaluate_agent(
            mcp_agent,
            test_suite="swe_bench_lite",
            limit=5
        )
        
        print("\n✅ Evaluation Complete!")
        print("\nKey Metrics:")
        print(f"  Task Completion Rate: {metrics.completed_tasks}/{metrics.total_tasks}")
        print(f"  Efficiency Score: {metrics.efficiency_score:.1f}/100")
        print(f"  Average Time: {metrics.average_time_per_task:.2f}s")
        print(f"  Throughput: {metrics.throughput:.2f} tasks/hour")
        
        # Show tool usage
        if metrics.tool_usage_distribution:
            print("\nTop Tools Used:")
            sorted_tools = sorted(
                metrics.tool_usage_distribution.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            for tool, count in sorted_tools:
                print(f"  - {tool}: {count} calls")
        
        # Save report
        report_path = Path("evaluation_report.html")
        with open(report_path, 'w') as f:
            f.write(report.generate_html())
        print(f"\n📄 HTML report saved to: {report_path}")
        
    except Exception as e:
        print(f"\nℹ️ Evaluation demo error (expected): {e}")
        print("In production, this would run against real MCP agents and tasks")


async def main():
    """Run all SWE-bench evaluation demos."""
    print("🌟 MCP Agent Reliability Lab - SWE-bench Evaluation Demos")
    print("=" * 60)
    
    # Setup telemetry
    setup_telemetry(service_name="swe-bench-evaluation-demo")
    
    try:
        # Run demos
        await swe_bench_basic_demo()
        await task_pipeline_demo()
        await custom_benchmarks_demo()
        await performance_metrics_demo()
        await comprehensive_evaluation_demo()
        
        print("\n🎉 All evaluation demos completed!")
        print("\nKey Features Demonstrated:")
        print("✅ SWE-bench dataset loading and caching")
        print("✅ Task-to-MCP sequence conversion")
        print("✅ Multi-stage execution pipeline")
        print("✅ Custom MCP-specific benchmarks")
        print("✅ Performance metrics collection")
        print("✅ Comprehensive reporting")
        print("✅ Parallel task execution")
        print("✅ Error recovery testing")
        print("✅ Resource utilization tracking")
        
        print("\nSupported Evaluations:")
        print("- SWE-bench Full, Lite, and Verified datasets")
        print("- Multi-tool coordination benchmarks")
        print("- Long-running operation tests")
        print("- Concurrent request handling")
        print("- State consistency verification")
        print("- Resource management tests")
        
        print("\nNext Steps:")
        print("- Connect real MCP agents for evaluation")
        print("- Run full SWE-bench dataset")
        print("- Create custom domain-specific benchmarks")
        print("- Set up continuous evaluation pipeline")
        print("- Compare different agent implementations")
        
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())