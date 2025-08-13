"""Task execution pipeline for SWE-bench and custom benchmarks."""

import asyncio
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import logging

from opentelemetry import trace, metrics

from ..core import MCPServerWrapper
from ..sandbox import SandboxManager, get_sandbox_template
from .swe_bench import SWEBenchTask, SWEBenchResult


logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Metrics
pipeline_executions = meter.create_counter(
    "evaluation.pipeline_executions",
    description="Number of pipeline executions"
)
stage_duration = meter.create_histogram(
    "evaluation.stage_duration",
    description="Duration of pipeline stages",
    unit="s"
)


class PipelineStage(str, Enum):
    """Pipeline execution stages."""
    
    SETUP = "setup"
    REPOSITORY_PREPARATION = "repository_preparation"
    AGENT_INVOCATION = "agent_invocation"
    PATCH_GENERATION = "patch_generation"
    PATCH_APPLICATION = "patch_application"
    TEST_EXECUTION = "test_execution"
    VALIDATION = "validation"
    CLEANUP = "cleanup"


@dataclass
class ExecutionConfig:
    """Configuration for task execution."""
    
    # Sandbox settings
    sandbox_template: str = "swe_bench"
    max_memory_mb: int = 4096
    max_cpu_cores: int = 4
    
    # Timeouts
    setup_timeout: int = 60
    agent_timeout: int = 300
    test_timeout: int = 120
    total_timeout: int = 600
    
    # Agent settings
    agent_model: str = "claude-3"
    agent_temperature: float = 0.0
    max_iterations: int = 10
    
    # Execution options
    use_cache: bool = True
    parallel_tests: bool = False
    verbose: bool = False
    collect_artifacts: bool = True
    
    # Resource limits
    max_file_size_mb: int = 10
    max_output_size_mb: int = 50
    
    # Retry settings
    retry_on_failure: bool = True
    max_retries: int = 3
    retry_delay: int = 5


@dataclass
class StageResult:
    """Result of a pipeline stage execution."""
    
    stage: PipelineStage
    success: bool
    duration: float
    output: Optional[Any] = None
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Complete result of task execution."""
    
    task_id: str
    success: bool
    total_duration: float
    
    # Stage results
    stages: List[StageResult] = field(default_factory=list)
    
    # Outputs
    generated_patch: Optional[str] = None
    test_results: Dict[str, Any] = field(default_factory=dict)
    validation_passed: bool = False
    
    # Agent details
    agent_iterations: int = 0
    tools_used: List[str] = field(default_factory=list)
    tokens_used: int = 0
    
    # Resource usage
    peak_memory_mb: float = 0.0
    cpu_seconds: float = 0.0
    
    # Artifacts
    artifacts: Dict[str, Any] = field(default_factory=dict)
    
    # Errors
    error: Optional[str] = None
    failed_stage: Optional[PipelineStage] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "success": self.success,
            "total_duration": self.total_duration,
            "stages": [
                {
                    "stage": s.stage,
                    "success": s.success,
                    "duration": s.duration,
                    "error": s.error
                }
                for s in self.stages
            ],
            "generated_patch": self.generated_patch,
            "test_results": self.test_results,
            "validation_passed": self.validation_passed,
            "agent_iterations": self.agent_iterations,
            "tools_used": self.tools_used,
            "peak_memory_mb": self.peak_memory_mb,
            "cpu_seconds": self.cpu_seconds,
            "error": self.error,
            "failed_stage": self.failed_stage
        }


class TaskExecutionPipeline:
    """Orchestrates task execution through multiple stages."""
    
    def __init__(
        self,
        mcp_wrapper: MCPServerWrapper,
        sandbox_manager: SandboxManager,
        config: Optional[ExecutionConfig] = None
    ):
        self.mcp_wrapper = mcp_wrapper
        self.sandbox_manager = sandbox_manager
        self.config = config or ExecutionConfig()
        self._stage_handlers: Dict[PipelineStage, Callable] = self._register_handlers()
        
    def _register_handlers(self) -> Dict[PipelineStage, Callable]:
        """Register stage handlers."""
        return {
            PipelineStage.SETUP: self._stage_setup,
            PipelineStage.REPOSITORY_PREPARATION: self._stage_repository_preparation,
            PipelineStage.AGENT_INVOCATION: self._stage_agent_invocation,
            PipelineStage.PATCH_GENERATION: self._stage_patch_generation,
            PipelineStage.PATCH_APPLICATION: self._stage_patch_application,
            PipelineStage.TEST_EXECUTION: self._stage_test_execution,
            PipelineStage.VALIDATION: self._stage_validation,
            PipelineStage.CLEANUP: self._stage_cleanup
        }
    
    async def execute_task(
        self,
        task: SWEBenchTask,
        custom_config: Optional[ExecutionConfig] = None
    ) -> ExecutionResult:
        """Execute a single task through the pipeline."""
        
        config = custom_config or self.config
        start_time = time.time()
        
        # Initialize result
        result = ExecutionResult(
            task_id=task.instance_id,
            success=False,
            total_duration=0.0
        )
        
        # Create execution context
        context = {
            "task": task,
            "config": config,
            "sandbox": None,
            "repository_path": None,
            "patch": None,
            "test_output": None
        }
        
        span = tracer.start_span(f"pipeline.execute_task.{task.instance_id}")
        pipeline_executions.add(1, {"task_type": "swe_bench"})
        
        try:
            # Execute pipeline stages
            for stage in PipelineStage:
                stage_result = await self._execute_stage(
                    stage,
                    context,
                    config
                )
                
                result.stages.append(stage_result)
                
                if not stage_result.success:
                    result.failed_stage = stage
                    result.error = stage_result.error
                    
                    # Retry logic
                    if config.retry_on_failure and stage != PipelineStage.CLEANUP:
                        for retry in range(config.max_retries):
                            logger.info(f"Retrying stage {stage} (attempt {retry + 1})")
                            await asyncio.sleep(config.retry_delay)
                            
                            stage_result = await self._execute_stage(
                                stage,
                                context,
                                config
                            )
                            
                            if stage_result.success:
                                result.stages[-1] = stage_result
                                break
                    
                    if not stage_result.success:
                        break
            
            # Extract results from context
            result.generated_patch = context.get("patch")
            result.test_results = context.get("test_output", {})
            result.validation_passed = context.get("validation_passed", False)
            result.success = result.validation_passed
            
            # Collect metrics
            result.agent_iterations = context.get("agent_iterations", 0)
            result.tools_used = context.get("tools_used", [])
            result.tokens_used = context.get("tokens_used", 0)
            
            # Collect artifacts if configured
            if config.collect_artifacts and context.get("sandbox"):
                result.artifacts = await self._collect_artifacts(
                    context["sandbox"],
                    task
                )
            
        except asyncio.TimeoutError:
            result.error = f"Pipeline timed out after {config.total_timeout}s"
            logger.error(f"Pipeline timeout for task {task.instance_id}")
            
        except Exception as e:
            result.error = str(e)
            logger.error(f"Pipeline error for task {task.instance_id}: {e}")
            
        finally:
            result.total_duration = time.time() - start_time
            span.set_attribute("pipeline.success", result.success)
            span.set_attribute("pipeline.duration", result.total_duration)
            span.end()
        
        return result
    
    async def execute_batch(
        self,
        tasks: List[SWEBenchTask],
        parallel: int = 1,
        progress_callback: Optional[Callable] = None
    ) -> List[ExecutionResult]:
        """Execute multiple tasks in batch."""
        
        if parallel == 1:
            # Sequential execution
            results = []
            for i, task in enumerate(tasks):
                result = await self.execute_task(task)
                results.append(result)
                
                if progress_callback:
                    progress_callback(i + 1, len(tasks), result)
                
                logger.info(f"Completed {i + 1}/{len(tasks)} tasks")
            
            return results
        
        # Parallel execution
        semaphore = asyncio.Semaphore(parallel)
        completed = 0
        results = []
        
        async def execute_with_limit(task, index):
            nonlocal completed
            async with semaphore:
                result = await self.execute_task(task)
                completed += 1
                
                if progress_callback:
                    progress_callback(completed, len(tasks), result)
                
                return index, result
        
        # Execute tasks
        tasks_list = [
            execute_with_limit(task, i)
            for i, task in enumerate(tasks)
        ]
        
        task_results = await asyncio.gather(*tasks_list, return_exceptions=True)
        
        # Sort results by original index
        sorted_results = [None] * len(tasks)
        for item in task_results:
            if isinstance(item, tuple):
                index, result = item
                sorted_results[index] = result
            else:
                # Handle exceptions
                sorted_results.append(ExecutionResult(
                    task_id="error",
                    success=False,
                    total_duration=0.0,
                    error=str(item)
                ))
        
        return [r for r in sorted_results if r is not None]
    
    async def _execute_stage(
        self,
        stage: PipelineStage,
        context: Dict[str, Any],
        config: ExecutionConfig
    ) -> StageResult:
        """Execute a single pipeline stage."""
        
        logger.info(f"Executing stage: {stage}")
        start_time = time.time()
        
        result = StageResult(
            stage=stage,
            success=False,
            duration=0.0
        )
        
        try:
            # Get handler for stage
            handler = self._stage_handlers.get(stage)
            if not handler:
                raise ValueError(f"No handler for stage {stage}")
            
            # Execute stage
            stage_output = await handler(context, config)
            
            result.success = True
            result.output = stage_output
            
        except Exception as e:
            result.error = str(e)
            logger.error(f"Stage {stage} failed: {e}")
            
        finally:
            result.duration = time.time() - start_time
            stage_duration.record(result.duration, {"stage": stage})
        
        return result
    
    async def _stage_setup(
        self,
        context: Dict[str, Any],
        config: ExecutionConfig
    ) -> Dict[str, Any]:
        """Setup stage: Create sandbox and prepare environment."""
        
        # Get sandbox template
        sandbox_config = get_sandbox_template(config.sandbox_template)
        
        # Customize resource limits
        sandbox_config.resources.memory = config.max_memory_mb
        sandbox_config.resources.cpu = config.max_cpu_cores
        
        # Create sandbox
        sandbox = await self.sandbox_manager.create_sandbox(sandbox_config)
        context["sandbox"] = sandbox
        
        # Install required tools
        await sandbox.execute(["apt-get", "update", "-qq"])
        await sandbox.execute([
            "apt-get", "install", "-qq", "-y",
            "git", "python3-pip", "build-essential"
        ])
        
        return {"sandbox_id": sandbox.sandbox_id}
    
    async def _stage_repository_preparation(
        self,
        context: Dict[str, Any],
        config: ExecutionConfig
    ) -> Dict[str, Any]:
        """Prepare repository in sandbox."""
        
        task = context["task"]
        sandbox = context["sandbox"]
        
        repo_name = task.repo.split('/')[-1]
        repo_path = f"/workspace/{repo_name}"
        
        # Clone repository
        await sandbox.execute([
            "git", "clone",
            "--depth", "50",  # Shallow clone for speed
            f"https://github.com/{task.repo}",
            repo_path
        ])
        
        # Checkout base commit
        await sandbox.execute([
            "git", "checkout", task.base_commit
        ], cwd=repo_path)
        
        # Install dependencies
        requirements_files = [
            "requirements.txt",
            "requirements-dev.txt",
            "setup.py"
        ]
        
        for req_file in requirements_files:
            req_path = Path(repo_path) / req_file
            if await sandbox.file_exists(str(req_path)):
                if req_file.endswith(".py"):
                    await sandbox.execute([
                        "pip", "install", "-e", "."
                    ], cwd=repo_path)
                else:
                    await sandbox.execute([
                        "pip", "install", "-r", req_file
                    ], cwd=repo_path)
        
        context["repository_path"] = repo_path
        
        return {"repository_path": repo_path}
    
    async def _stage_agent_invocation(
        self,
        context: Dict[str, Any],
        config: ExecutionConfig
    ) -> Dict[str, Any]:
        """Invoke MCP agent to solve the task."""
        
        task = context["task"]
        sandbox = context["sandbox"]
        repo_path = context["repository_path"]
        
        # Prepare agent context
        agent_prompt = f"""
Task: Solve the following GitHub issue.

Repository: {task.repo}
Base Commit: {task.base_commit}
Working Directory: {repo_path}

Issue Description:
{task.problem_statement}

{f"Hints: {task.hints_text}" if task.hints_text else ""}

Instructions:
1. Analyze the issue and understand what needs to be fixed
2. Explore the repository structure to find relevant files
3. Read and understand the existing code
4. Generate a patch that fixes the issue
5. The patch should be minimal and focused on the problem

You have access to these tools:
- read_file: Read file contents
- write_file: Write file contents
- edit_file: Edit specific lines in a file
- list_directory: List directory contents
- search_code: Search for code patterns
- run_command: Execute shell commands

Generate a solution and return it as a unified diff patch.
"""
        
        # Track tool usage
        tools_used = []
        iterations = 0
        
        # Invoke agent
        for iteration in range(config.max_iterations):
            iterations += 1
            
            response = await self.mcp_wrapper.call_tool(
                "solve_task",
                {
                    "prompt": agent_prompt,
                    "sandbox_id": sandbox.sandbox_id,
                    "temperature": config.agent_temperature,
                    "max_tokens": 4000
                }
            )
            
            # Track tools
            if "tools_used" in response:
                tools_used.extend(response["tools_used"])
            
            # Check if solution is complete
            if response.get("complete", False):
                break
            
            # Update prompt for next iteration
            agent_prompt = f"""
Previous attempt didn't complete the solution.
Continue working on the issue.

{response.get('feedback', '')}
"""
        
        context["agent_response"] = response
        context["agent_iterations"] = iterations
        context["tools_used"] = tools_used
        
        return {
            "iterations": iterations,
            "tools_used": len(set(tools_used))
        }
    
    async def _stage_patch_generation(
        self,
        context: Dict[str, Any],
        config: ExecutionConfig
    ) -> Dict[str, Any]:
        """Generate patch from agent response."""
        
        agent_response = context.get("agent_response", {})
        
        # Extract patch from response
        patch = agent_response.get("patch")
        
        if not patch:
            # Try to generate patch from file changes
            changes = agent_response.get("file_changes", [])
            if changes:
                patch = await self._generate_patch_from_changes(
                    context["sandbox"],
                    context["repository_path"],
                    changes
                )
        
        if not patch:
            raise ValueError("No patch generated by agent")
        
        context["patch"] = patch
        
        return {"patch_size": len(patch)}
    
    async def _stage_patch_application(
        self,
        context: Dict[str, Any],
        config: ExecutionConfig
    ) -> Dict[str, Any]:
        """Apply generated patch to repository."""
        
        sandbox = context["sandbox"]
        repo_path = context["repository_path"]
        patch = context["patch"]
        
        # Save patch to file
        patch_file = f"{repo_path}/generated.patch"
        await sandbox.write_file(patch_file, patch)
        
        # Apply patch
        result = await sandbox.execute([
            "git", "apply", "--check", patch_file
        ], cwd=repo_path)
        
        if result.exit_code != 0:
            # Try with --3way for better conflict resolution
            result = await sandbox.execute([
                "git", "apply", "--3way", patch_file
            ], cwd=repo_path)
        else:
            result = await sandbox.execute([
                "git", "apply", patch_file
            ], cwd=repo_path)
        
        if result.exit_code != 0:
            raise ValueError(f"Failed to apply patch: {result.stderr}")
        
        return {"patch_applied": True}
    
    async def _stage_test_execution(
        self,
        context: Dict[str, Any],
        config: ExecutionConfig
    ) -> Dict[str, Any]:
        """Execute tests to validate the fix."""
        
        task = context["task"]
        sandbox = context["sandbox"]
        repo_path = context["repository_path"]
        
        test_results = {
            "passed": [],
            "failed": [],
            "output": ""
        }
        
        # Run test command if provided
        if task.test_cmd:
            result = await sandbox.execute(
                task.test_cmd,
                cwd=repo_path,
                timeout=config.test_timeout,
                capture_output=True
            )
            
            test_results["output"] = result.stdout + result.stderr
            test_results["exit_code"] = result.exit_code
            
            # Parse test results
            test_results = self._parse_test_output(
                test_results["output"],
                task
            )
        
        context["test_output"] = test_results
        
        return test_results
    
    async def _stage_validation(
        self,
        context: Dict[str, Any],
        config: ExecutionConfig
    ) -> Dict[str, Any]:
        """Validate that the fix meets requirements."""
        
        task = context["task"]
        test_results = context.get("test_output", {})
        
        validation_passed = True
        validation_details = {
            "fail_to_pass": [],
            "pass_to_pass": []
        }
        
        # Check fail_to_pass tests
        for test in task.fail_to_pass:
            if test in test_results.get("passed", []):
                validation_details["fail_to_pass"].append({
                    "test": test,
                    "status": "passed"
                })
            else:
                validation_details["fail_to_pass"].append({
                    "test": test,
                    "status": "failed"
                })
                validation_passed = False
        
        # Check pass_to_pass tests
        for test in task.pass_to_pass:
            if test in test_results.get("passed", []):
                validation_details["pass_to_pass"].append({
                    "test": test,
                    "status": "passed"
                })
            else:
                validation_details["pass_to_pass"].append({
                    "test": test,
                    "status": "failed"
                })
                validation_passed = False
        
        context["validation_passed"] = validation_passed
        context["validation_details"] = validation_details
        
        return validation_details
    
    async def _stage_cleanup(
        self,
        context: Dict[str, Any],
        config: ExecutionConfig
    ) -> Dict[str, Any]:
        """Cleanup stage: Clean up resources."""
        
        sandbox = context.get("sandbox")
        
        if sandbox:
            # Collect final metrics
            metrics = await sandbox.get_metrics()
            context["final_metrics"] = metrics
            
            # Destroy sandbox
            await self.sandbox_manager.destroy_sandbox(sandbox.sandbox_id)
        
        return {"cleaned_up": True}
    
    async def _generate_patch_from_changes(
        self,
        sandbox,
        repo_path: str,
        changes: List[Dict[str, Any]]
    ) -> str:
        """Generate unified diff patch from file changes."""
        
        # Create a git commit with changes
        for change in changes:
            file_path = change["file"]
            content = change["content"]
            
            await sandbox.write_file(
                f"{repo_path}/{file_path}",
                content
            )
        
        # Generate patch
        result = await sandbox.execute([
            "git", "diff", "--no-index", "--unified=3"
        ], cwd=repo_path)
        
        return result.stdout
    
    def _parse_test_output(
        self,
        output: str,
        task: SWEBenchTask
    ) -> Dict[str, Any]:
        """Parse test output to extract results."""
        
        passed = []
        failed = []
        
        # Common test output patterns
        patterns = {
            "pytest": {
                "passed": r"(\S+)\s+PASSED",
                "failed": r"(\S+)\s+FAILED"
            },
            "unittest": {
                "passed": r"(\S+)\s+\.\.\.\s+ok",
                "failed": r"(\S+)\s+\.\.\.\s+FAIL"
            }
        }
        
        # Try to detect test framework and parse
        import re
        
        for framework, pattern_set in patterns.items():
            if framework in output.lower():
                # Extract passed tests
                for match in re.finditer(pattern_set["passed"], output):
                    passed.append(match.group(1))
                
                # Extract failed tests
                for match in re.finditer(pattern_set["failed"], output):
                    failed.append(match.group(1))
        
        return {
            "passed": passed,
            "failed": failed,
            "output": output
        }
    
    async def _collect_artifacts(
        self,
        sandbox,
        task: SWEBenchTask
    ) -> Dict[str, Any]:
        """Collect artifacts from execution."""
        
        artifacts = {}
        
        # Collect generated patch
        patch_file = f"/workspace/{task.repo.split('/')[-1]}/generated.patch"
        if await sandbox.file_exists(patch_file):
            artifacts["patch"] = await sandbox.read_file(patch_file)
        
        # Collect test output
        test_log = "/tmp/test_output.log"
        if await sandbox.file_exists(test_log):
            artifacts["test_log"] = await sandbox.read_file(test_log)
        
        # Collect agent logs
        agent_log = "/tmp/agent.log"
        if await sandbox.file_exists(agent_log):
            artifacts["agent_log"] = await sandbox.read_file(agent_log)
        
        return artifacts