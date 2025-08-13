"""SWE-bench adapter for MCP agent evaluation."""

import asyncio
import json
import hashlib
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import logging

import aiohttp
import aiofiles
from pydantic import BaseModel, Field

from ..core import MCPServerWrapper
from ..sandbox import SandboxManager, get_sandbox_template


logger = logging.getLogger(__name__)


class DatasetType(str, Enum):
    """SWE-bench dataset types."""
    
    FULL = "full"
    LITE = "lite"
    VERIFIED = "verified"
    
    def get_url(self) -> str:
        """Get dataset download URL."""
        base_url = "https://github.com/princeton-nlp/SWE-bench/raw/main/data"
        urls = {
            DatasetType.FULL: f"{base_url}/swe-bench.json",
            DatasetType.LITE: f"{base_url}/swe-bench-lite.json",
            DatasetType.VERIFIED: f"{base_url}/swe-bench-verified.json"
        }
        return urls.get(self, urls[DatasetType.LITE])


@dataclass
class SWEBenchTask:
    """Represents a single SWE-bench task."""
    
    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str
    hints_text: Optional[str] = None
    created_at: Optional[str] = None
    
    # Test information
    test_patch: Optional[str] = None
    test_directives: List[str] = field(default_factory=list)
    test_cmd: Optional[str] = None
    
    # Solution information
    patch: Optional[str] = None
    model_patch: Optional[str] = None
    model_name_or_path: Optional[str] = None
    
    # Evaluation
    pass_to_pass: List[str] = field(default_factory=list)
    fail_to_pass: List[str] = field(default_factory=list)
    
    # MCP-specific fields
    mcp_tools_sequence: List[Dict[str, Any]] = field(default_factory=list)
    sandbox_config: Optional[Dict[str, Any]] = None
    
    def to_mcp_format(self) -> Dict[str, Any]:
        """Convert task to MCP tool sequence format."""
        return {
            "task_id": self.instance_id,
            "description": self.problem_statement,
            "repository": {
                "url": f"https://github.com/{self.repo}",
                "commit": self.base_commit
            },
            "tools_sequence": self._generate_mcp_sequence(),
            "validation": {
                "test_command": self.test_cmd,
                "expected_pass": self.fail_to_pass,
                "expected_maintain": self.pass_to_pass
            }
        }
    
    def _generate_mcp_sequence(self) -> List[Dict[str, Any]]:
        """Generate MCP tool sequence for the task."""
        sequence = []
        
        # 1. Clone repository
        sequence.append({
            "tool": "git_clone",
            "parameters": {
                "repository": f"https://github.com/{self.repo}",
                "directory": f"/workspace/{self.repo.split('/')[-1]}"
            }
        })
        
        # 2. Checkout base commit
        sequence.append({
            "tool": "git_checkout",
            "parameters": {
                "commit": self.base_commit,
                "directory": f"/workspace/{self.repo.split('/')[-1]}"
            }
        })
        
        # 3. Read problem statement
        sequence.append({
            "tool": "read_issue",
            "parameters": {
                "content": self.problem_statement
            }
        })
        
        # 4. Explore repository structure
        sequence.append({
            "tool": "list_files",
            "parameters": {
                "directory": f"/workspace/{self.repo.split('/')[-1]}",
                "recursive": True,
                "max_depth": 3
            }
        })
        
        # 5. Run initial tests (if available)
        if self.test_cmd:
            sequence.append({
                "tool": "run_command",
                "parameters": {
                    "command": self.test_cmd,
                    "directory": f"/workspace/{self.repo.split('/')[-1]}",
                    "capture_output": True
                }
            })
        
        return sequence


@dataclass
class SWEBenchResult:
    """Result of a SWE-bench task execution."""
    
    task_id: str
    success: bool
    execution_time: float
    
    # Test results
    tests_passed: List[str] = field(default_factory=list)
    tests_failed: List[str] = field(default_factory=list)
    test_output: Optional[str] = None
    
    # Patch information
    generated_patch: Optional[str] = None
    patch_applied: bool = False
    
    # MCP execution details
    tools_used: List[str] = field(default_factory=list)
    tool_calls_count: int = 0
    
    # Resource usage
    cpu_time: float = 0.0
    memory_peak_mb: float = 0.0
    
    # Errors
    error: Optional[str] = None
    traceback: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "task_id": self.task_id,
            "success": self.success,
            "execution_time": self.execution_time,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "test_output": self.test_output,
            "generated_patch": self.generated_patch,
            "patch_applied": self.patch_applied,
            "tools_used": self.tools_used,
            "tool_calls_count": self.tool_calls_count,
            "cpu_time": self.cpu_time,
            "memory_peak_mb": self.memory_peak_mb,
            "error": self.error
        }
    
    @property
    def pass_rate(self) -> float:
        """Calculate test pass rate."""
        total = len(self.tests_passed) + len(self.tests_failed)
        if total == 0:
            return 0.0
        return len(self.tests_passed) / total


class SWEBenchDataset:
    """Manages SWE-bench dataset loading and caching."""
    
    def __init__(self, cache_dir: Path = Path.home() / ".cache" / "swe-bench"):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.tasks: Dict[str, SWEBenchTask] = {}
        
    async def load_dataset(
        self,
        dataset_type: DatasetType = DatasetType.LITE,
        force_download: bool = False
    ) -> List[SWEBenchTask]:
        """Load SWE-bench dataset with caching."""
        
        cache_file = self.cache_dir / f"swe-bench-{dataset_type.value}.json"
        
        # Check cache
        if cache_file.exists() and not force_download:
            logger.info(f"Loading cached dataset from {cache_file}")
            return await self._load_from_cache(cache_file)
        
        # Download dataset
        logger.info(f"Downloading SWE-bench {dataset_type.value} dataset...")
        data = await self._download_dataset(dataset_type)
        
        # Save to cache
        await self._save_to_cache(cache_file, data)
        
        # Parse tasks
        tasks = self._parse_dataset(data)
        
        # Store in memory
        for task in tasks:
            self.tasks[task.instance_id] = task
        
        return tasks
    
    async def _download_dataset(self, dataset_type: DatasetType) -> List[Dict[str, Any]]:
        """Download dataset from GitHub."""
        url = dataset_type.get_url()
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise ValueError(f"Failed to download dataset: HTTP {response.status}")
                
                content = await response.text()
                return json.loads(content)
    
    async def _load_from_cache(self, cache_file: Path) -> List[SWEBenchTask]:
        """Load dataset from cache file."""
        async with aiofiles.open(cache_file, 'r') as f:
            content = await f.read()
            data = json.loads(content)
            return self._parse_dataset(data)
    
    async def _save_to_cache(self, cache_file: Path, data: List[Dict[str, Any]]) -> None:
        """Save dataset to cache file."""
        async with aiofiles.open(cache_file, 'w') as f:
            await f.write(json.dumps(data, indent=2))
    
    def _parse_dataset(self, data: List[Dict[str, Any]]) -> List[SWEBenchTask]:
        """Parse raw dataset into SWEBenchTask objects."""
        tasks = []
        
        for item in data:
            task = SWEBenchTask(
                instance_id=item.get("instance_id", ""),
                repo=item.get("repo", ""),
                base_commit=item.get("base_commit", ""),
                problem_statement=item.get("problem_statement", ""),
                hints_text=item.get("hints_text"),
                created_at=item.get("created_at"),
                test_patch=item.get("test_patch"),
                test_cmd=item.get("test_cmd"),
                patch=item.get("patch"),
                model_patch=item.get("model_patch"),
                model_name_or_path=item.get("model_name_or_path"),
                pass_to_pass=item.get("pass_to_pass", []),
                fail_to_pass=item.get("fail_to_pass", [])
            )
            
            # Generate MCP sequence
            task.mcp_tools_sequence = task._generate_mcp_sequence()
            
            tasks.append(task)
        
        return tasks
    
    def get_task(self, task_id: str) -> Optional[SWEBenchTask]:
        """Get a specific task by ID."""
        return self.tasks.get(task_id)
    
    def filter_tasks(
        self,
        repo: Optional[str] = None,
        difficulty: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[SWEBenchTask]:
        """Filter tasks based on criteria."""
        filtered = list(self.tasks.values())
        
        if repo:
            filtered = [t for t in filtered if repo in t.repo]
        
        # Add more filtering logic as needed
        
        if limit:
            filtered = filtered[:limit]
        
        return filtered


class SWEBenchAdapter:
    """Adapter for running SWE-bench tasks with MCP agents."""
    
    def __init__(
        self,
        mcp_wrapper: MCPServerWrapper,
        sandbox_manager: SandboxManager,
        cache_dir: Optional[Path] = None
    ):
        self.mcp_wrapper = mcp_wrapper
        self.sandbox_manager = sandbox_manager
        self.dataset = SWEBenchDataset(cache_dir or Path.home() / ".cache" / "swe-bench")
        self.results_cache: Dict[str, SWEBenchResult] = {}
        
    async def load_dataset(
        self,
        dataset_type: DatasetType = DatasetType.LITE
    ) -> List[SWEBenchTask]:
        """Load SWE-bench dataset."""
        return await self.dataset.load_dataset(dataset_type)
    
    async def run_task(
        self,
        task: SWEBenchTask,
        sandbox_template: str = "swe_bench",
        timeout: int = 300,
        use_cache: bool = True
    ) -> SWEBenchResult:
        """Run a single SWE-bench task."""
        
        # Check cache
        if use_cache and task.instance_id in self.results_cache:
            logger.info(f"Using cached result for {task.instance_id}")
            return self.results_cache[task.instance_id]
        
        logger.info(f"Running SWE-bench task: {task.instance_id}")
        start_time = datetime.now()
        
        # Create result object
        result = SWEBenchResult(
            task_id=task.instance_id,
            success=False,
            execution_time=0.0
        )
        
        try:
            # Get sandbox configuration
            sandbox_config = get_sandbox_template(sandbox_template)
            
            # Create sandbox
            async with self.sandbox_manager.sandbox_context(sandbox_config) as sandbox:
                logger.info(f"Created sandbox: {sandbox.sandbox_id}")
                
                # Setup repository in sandbox
                await self._setup_repository(sandbox, task)
                
                # Convert task to MCP format
                mcp_task = task.to_mcp_format()
                
                # Execute MCP tool sequence
                for tool_call in mcp_task["tools_sequence"]:
                    tool_name = tool_call["tool"]
                    parameters = tool_call.get("parameters", {})
                    
                    # Map to MCP tools
                    mcp_response = await self._execute_mcp_tool(
                        tool_name,
                        parameters,
                        sandbox
                    )
                    
                    result.tools_used.append(tool_name)
                    result.tool_calls_count += 1
                
                # Let agent solve the problem
                agent_response = await self._invoke_agent(task, sandbox)
                
                # Apply generated patch
                if agent_response.get("patch"):
                    result.generated_patch = agent_response["patch"]
                    result.patch_applied = await self._apply_patch(
                        sandbox,
                        agent_response["patch"],
                        task
                    )
                
                # Run tests
                test_results = await self._run_tests(sandbox, task)
                result.tests_passed = test_results["passed"]
                result.tests_failed = test_results["failed"]
                result.test_output = test_results["output"]
                
                # Check success
                result.success = self._check_success(task, test_results)
                
                # Collect metrics
                metrics = await self._collect_metrics(sandbox)
                result.cpu_time = metrics.get("cpu_time", 0.0)
                result.memory_peak_mb = metrics.get("memory_peak_mb", 0.0)
                
        except asyncio.TimeoutError:
            result.error = f"Task timed out after {timeout} seconds"
            logger.error(f"Task {task.instance_id} timed out")
            
        except Exception as e:
            result.error = str(e)
            result.traceback = traceback.format_exc()
            logger.error(f"Task {task.instance_id} failed: {e}")
        
        finally:
            # Calculate execution time
            result.execution_time = (datetime.now() - start_time).total_seconds()
            
            # Cache result
            if use_cache:
                self.results_cache[task.instance_id] = result
        
        return result
    
    async def run_benchmark(
        self,
        tasks: List[SWEBenchTask],
        parallel: int = 1,
        sandbox_template: str = "swe_bench"
    ) -> List[SWEBenchResult]:
        """Run multiple SWE-bench tasks."""
        
        if parallel == 1:
            # Sequential execution
            results = []
            for task in tasks:
                result = await self.run_task(task, sandbox_template)
                results.append(result)
                logger.info(f"Completed {len(results)}/{len(tasks)} tasks")
            return results
        
        # Parallel execution
        semaphore = asyncio.Semaphore(parallel)
        
        async def run_with_limit(task):
            async with semaphore:
                return await self.run_task(task, sandbox_template)
        
        tasks_list = [run_with_limit(task) for task in tasks]
        results = await asyncio.gather(*tasks_list, return_exceptions=True)
        
        # Process results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Create error result
                error_result = SWEBenchResult(
                    task_id=tasks[i].instance_id,
                    success=False,
                    execution_time=0.0,
                    error=str(result)
                )
                processed_results.append(error_result)
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _setup_repository(self, sandbox, task: SWEBenchTask) -> None:
        """Setup repository in sandbox."""
        repo_name = task.repo.split('/')[-1]
        
        # Clone repository
        await sandbox.execute([
            "git", "clone",
            f"https://github.com/{task.repo}",
            f"/workspace/{repo_name}"
        ])
        
        # Checkout base commit
        await sandbox.execute([
            "git", "checkout", task.base_commit
        ], cwd=f"/workspace/{repo_name}")
        
        # Install dependencies if needed
        if Path(f"/workspace/{repo_name}/requirements.txt").exists():
            await sandbox.execute([
                "pip", "install", "-r", "requirements.txt"
            ], cwd=f"/workspace/{repo_name}")
    
    async def _execute_mcp_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        sandbox
    ) -> Dict[str, Any]:
        """Execute an MCP tool in the sandbox context."""
        
        # Map SWE-bench operations to MCP tools
        tool_mapping = {
            "git_clone": "shell_command",
            "git_checkout": "shell_command",
            "read_issue": "read_file",
            "list_files": "list_directory",
            "run_command": "shell_command",
            "edit_file": "edit_file",
            "create_file": "write_file"
        }
        
        mcp_tool = tool_mapping.get(tool_name, tool_name)
        
        # Adapt parameters for MCP format
        if mcp_tool == "shell_command":
            if tool_name == "git_clone":
                parameters = {
                    "command": f"git clone {parameters['repository']} {parameters['directory']}"
                }
            elif tool_name == "git_checkout":
                parameters = {
                    "command": f"cd {parameters['directory']} && git checkout {parameters['commit']}"
                }
        
        # Execute through MCP wrapper
        return await self.mcp_wrapper.call_tool(mcp_tool, parameters)
    
    async def _invoke_agent(
        self,
        task: SWEBenchTask,
        sandbox
    ) -> Dict[str, Any]:
        """Invoke the MCP agent to solve the task."""
        
        # Prepare agent prompt
        prompt = f"""
You are tasked with solving a GitHub issue. Here are the details:

Repository: {task.repo}
Base Commit: {task.base_commit}

Problem Statement:
{task.problem_statement}

{f"Hints: {task.hints_text}" if task.hints_text else ""}

Please analyze the issue and generate a patch that fixes the problem.
The patch should be in unified diff format.

Available tools:
- read_file: Read file contents
- write_file: Write file contents
- edit_file: Edit specific lines in a file
- list_directory: List directory contents
- shell_command: Execute shell commands
- search_code: Search for code patterns

Return your solution as a patch in unified diff format.
"""
        
        # Call agent through MCP
        response = await self.mcp_wrapper.call_tool(
            "solve_issue",
            {"prompt": prompt, "sandbox_id": sandbox.sandbox_id}
        )
        
        return response
    
    async def _apply_patch(
        self,
        sandbox,
        patch: str,
        task: SWEBenchTask
    ) -> bool:
        """Apply a patch to the repository."""
        repo_name = task.repo.split('/')[-1]
        patch_file = f"/workspace/{repo_name}/generated.patch"
        
        try:
            # Write patch to file
            await sandbox.write_file(patch_file, patch)
            
            # Apply patch
            result = await sandbox.execute([
                "git", "apply", patch_file
            ], cwd=f"/workspace/{repo_name}")
            
            return result.exit_code == 0
            
        except Exception as e:
            logger.error(f"Failed to apply patch: {e}")
            return False
    
    async def _run_tests(
        self,
        sandbox,
        task: SWEBenchTask
    ) -> Dict[str, Any]:
        """Run tests in the sandbox."""
        repo_name = task.repo.split('/')[-1]
        
        # Run test command
        if task.test_cmd:
            result = await sandbox.execute(
                task.test_cmd.split(),
                cwd=f"/workspace/{repo_name}",
                capture_output=True
            )
            
            # Parse test output
            output = result.stdout + result.stderr
            
            # Simple parsing - can be enhanced
            passed = []
            failed = []
            
            for line in output.split('\n'):
                if 'PASSED' in line or '✓' in line:
                    # Extract test name
                    test_name = line.split()[0] if line.split() else "unknown"
                    passed.append(test_name)
                elif 'FAILED' in line or '✗' in line:
                    test_name = line.split()[0] if line.split() else "unknown"
                    failed.append(test_name)
            
            return {
                "passed": passed,
                "failed": failed,
                "output": output
            }
        
        return {"passed": [], "failed": [], "output": "No test command provided"}
    
    def _check_success(
        self,
        task: SWEBenchTask,
        test_results: Dict[str, Any]
    ) -> bool:
        """Check if the task was successfully solved."""
        
        # Check if all fail_to_pass tests now pass
        for test in task.fail_to_pass:
            if test not in test_results["passed"]:
                return False
        
        # Check if all pass_to_pass tests still pass
        for test in task.pass_to_pass:
            if test not in test_results["passed"]:
                return False
        
        return True
    
    async def _collect_metrics(self, sandbox) -> Dict[str, Any]:
        """Collect performance metrics from sandbox."""
        
        # Get resource usage
        result = await sandbox.execute([
            "ps", "aux", "--sort=-pcpu", "|", "head", "-5"
        ])
        
        # Parse CPU and memory usage (simplified)
        metrics = {
            "cpu_time": 0.0,
            "memory_peak_mb": 0.0
        }
        
        # In production, would parse actual metrics
        return metrics
    
    def get_statistics(self, results: List[SWEBenchResult]) -> Dict[str, Any]:
        """Calculate statistics from results."""
        
        if not results:
            return {}
        
        total = len(results)
        successful = sum(1 for r in results if r.success)
        
        # Calculate averages
        avg_time = sum(r.execution_time for r in results) / total
        avg_tools = sum(r.tool_calls_count for r in results) / total
        
        # Pass rates
        pass_rates = [r.pass_rate for r in results if r.tests_passed or r.tests_failed]
        avg_pass_rate = sum(pass_rates) / len(pass_rates) if pass_rates else 0
        
        return {
            "total_tasks": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": successful / total,
            "average_execution_time": avg_time,
            "average_tool_calls": avg_tools,
            "average_test_pass_rate": avg_pass_rate,
            "tools_usage": self._analyze_tools_usage(results)
        }
    
    def _analyze_tools_usage(self, results: List[SWEBenchResult]) -> Dict[str, int]:
        """Analyze tool usage patterns."""
        tool_counts = {}
        
        for result in results:
            for tool in result.tools_used:
                tool_counts[tool] = tool_counts.get(tool, 0) + 1
        
        return tool_counts


# Import for traceback
import traceback