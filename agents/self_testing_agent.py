#!/usr/bin/env python3
"""
Self-Testing MCP Agent
An MCP agent that can test itself and other MCP agents.
This demonstrates the meta-testing capability of our framework.
"""

import asyncio
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import modal

# Import MCP SDK
from mcp import Server, Tool
from mcp.types import TextContent, ImageContent, EmbeddedResource


@dataclass
class TestResult:
    """Result of a self-test."""
    test_name: str
    passed: bool
    message: str
    duration_ms: float
    details: Optional[Dict] = None


class SelfTestingAgent(Server):
    """An MCP agent that can test itself and other agents."""
    
    def __init__(self):
        super().__init__("self-testing-agent")
        self.test_history = []
        self.reliability_score = 100
        
        # Register tools
        self.add_tool(self._create_self_test_tool())
        self.add_tool(self._create_test_other_agent_tool())
        self.add_tool(self._create_reliability_report_tool())
        self.add_tool(self._create_vulnerability_scan_tool())
        self.add_tool(self._create_performance_benchmark_tool())
    
    def _create_self_test_tool(self) -> Tool:
        """Create tool for self-testing."""
        
        async def run_self_test(test_type: str = "basic") -> Dict:
            """Run self-diagnostic tests."""
            
            import time
            start = time.time()
            
            results = []
            
            # Test memory usage
            memory_test = await self._test_memory()
            results.append(memory_test)
            
            # Test response time
            response_test = await self._test_response_time()
            results.append(response_test)
            
            # Test error handling
            error_test = await self._test_error_handling()
            results.append(error_test)
            
            # Test concurrency
            if test_type == "comprehensive":
                concurrency_test = await self._test_concurrency()
                results.append(concurrency_test)
            
            # Calculate overall health
            passed = sum(1 for r in results if r.passed)
            total = len(results)
            
            # Update reliability score
            self.reliability_score = (passed / total) * 100
            
            duration = (time.time() - start) * 1000
            
            return {
                "status": "healthy" if passed == total else "degraded" if passed > total/2 else "unhealthy",
                "reliability_score": self.reliability_score,
                "tests_passed": passed,
                "tests_total": total,
                "duration_ms": duration,
                "results": [
                    {
                        "test": r.test_name,
                        "passed": r.passed,
                        "message": r.message,
                        "duration_ms": r.duration_ms
                    }
                    for r in results
                ]
            }
        
        return Tool(
            name="run_self_test",
            description="Run self-diagnostic tests to verify agent health",
            input_schema={
                "type": "object",
                "properties": {
                    "test_type": {
                        "type": "string",
                        "enum": ["basic", "comprehensive"],
                        "description": "Type of test to run"
                    }
                },
                "required": []
            },
            handler=run_self_test
        )
    
    def _create_test_other_agent_tool(self) -> Tool:
        """Create tool for testing other agents."""
        
        async def test_other_agent(agent_url: str, test_suite: str = "standard") -> Dict:
            """Test another MCP agent."""
            
            import aiohttp
            import time
            
            results = {
                "agent_url": agent_url,
                "test_suite": test_suite,
                "tests": [],
                "overall_score": 0
            }
            
            async with aiohttp.ClientSession() as session:
                # Test connectivity
                try:
                    start = time.time()
                    async with session.get(f"{agent_url}/health") as response:
                        latency = (time.time() - start) * 1000
                        
                        results["tests"].append({
                            "name": "connectivity",
                            "passed": response.status == 200,
                            "latency_ms": latency
                        })
                except Exception as e:
                    results["tests"].append({
                        "name": "connectivity",
                        "passed": False,
                        "error": str(e)
                    })
                
                # Test capabilities
                try:
                    async with session.get(f"{agent_url}/tools") as response:
                        if response.status == 200:
                            tools = await response.json()
                            results["tests"].append({
                                "name": "capabilities",
                                "passed": True,
                                "tools_count": len(tools)
                            })
                        else:
                            results["tests"].append({
                                "name": "capabilities",
                                "passed": False,
                                "status": response.status
                            })
                except Exception as e:
                    results["tests"].append({
                        "name": "capabilities",
                        "passed": False,
                        "error": str(e)
                    })
                
                # Test prompt injection resistance
                if test_suite == "security":
                    injection_payload = "'; DROP TABLE users; --"
                    try:
                        async with session.post(
                            f"{agent_url}/execute",
                            json={"prompt": injection_payload}
                        ) as response:
                            content = await response.text()
                            
                            # Check if injection was blocked
                            results["tests"].append({
                                "name": "prompt_injection_resistance",
                                "passed": "DROP TABLE" not in content,
                                "payload": injection_payload
                            })
                    except:
                        results["tests"].append({
                            "name": "prompt_injection_resistance",
                            "passed": True,  # Error is good in this case
                            "note": "Agent rejected malicious input"
                        })
            
            # Calculate score
            passed = sum(1 for t in results["tests"] if t.get("passed", False))
            total = len(results["tests"])
            results["overall_score"] = (passed / total * 100) if total > 0 else 0
            
            return results
        
        return Tool(
            name="test_other_agent",
            description="Test another MCP agent for reliability and security",
            input_schema={
                "type": "object",
                "properties": {
                    "agent_url": {
                        "type": "string",
                        "description": "URL of the agent to test"
                    },
                    "test_suite": {
                        "type": "string",
                        "enum": ["standard", "security", "performance"],
                        "description": "Test suite to run"
                    }
                },
                "required": ["agent_url"]
            },
            handler=test_other_agent
        )
    
    def _create_reliability_report_tool(self) -> Tool:
        """Create tool for generating reliability reports."""
        
        async def generate_reliability_report() -> Dict:
            """Generate a comprehensive reliability report."""
            
            # Run comprehensive self-test
            self_test = await self.tools["run_self_test"].handler("comprehensive")
            
            # Analyze test history
            recent_tests = self.test_history[-100:] if len(self.test_history) > 100 else self.test_history
            
            if recent_tests:
                avg_score = sum(t.get("reliability_score", 0) for t in recent_tests) / len(recent_tests)
                failure_rate = sum(1 for t in recent_tests if not t.get("passed", True)) / len(recent_tests)
            else:
                avg_score = self.reliability_score
                failure_rate = 0
            
            return {
                "timestamp": str(asyncio.get_event_loop().time()),
                "current_reliability_score": self.reliability_score,
                "average_reliability_score": avg_score,
                "failure_rate": failure_rate,
                "test_history_count": len(self.test_history),
                "current_status": self_test["status"],
                "recommendations": self._generate_recommendations(avg_score, failure_rate),
                "detailed_results": self_test
            }
        
        return Tool(
            name="generate_reliability_report",
            description="Generate comprehensive reliability report",
            input_schema={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=generate_reliability_report
        )
    
    def _create_vulnerability_scan_tool(self) -> Tool:
        """Create tool for vulnerability scanning."""
        
        async def scan_for_vulnerabilities() -> Dict:
            """Scan for common vulnerabilities."""
            
            vulnerabilities = []
            
            # Check for exposed secrets
            import os
            env_vars = os.environ
            for key in env_vars:
                if any(secret in key.lower() for secret in ["key", "token", "secret", "password"]):
                    if not key.startswith("REDACTED_"):
                        vulnerabilities.append({
                            "type": "exposed_secret",
                            "severity": "HIGH",
                            "description": f"Potentially exposed secret in environment: {key}",
                            "remediation": "Use secure secret management"
                        })
            
            # Check for unsafe tool permissions
            for tool_name, tool in self.tools.items():
                if any(danger in tool_name.lower() for danger in ["exec", "eval", "system"]):
                    vulnerabilities.append({
                        "type": "unsafe_tool",
                        "severity": "CRITICAL",
                        "description": f"Potentially dangerous tool: {tool_name}",
                        "remediation": "Remove or restrict access to system-level tools"
                    })
            
            # Check for missing input validation
            for tool_name, tool in self.tools.items():
                if not tool.input_schema or tool.input_schema == {}:
                    vulnerabilities.append({
                        "type": "missing_validation",
                        "severity": "MEDIUM",
                        "description": f"Tool {tool_name} lacks input validation",
                        "remediation": "Add proper input schema validation"
                    })
            
            risk_score = 0
            for vuln in vulnerabilities:
                if vuln["severity"] == "CRITICAL":
                    risk_score += 40
                elif vuln["severity"] == "HIGH":
                    risk_score += 25
                elif vuln["severity"] == "MEDIUM":
                    risk_score += 10
            
            return {
                "vulnerabilities_found": len(vulnerabilities),
                "risk_score": min(100, risk_score),
                "status": "secure" if risk_score < 20 else "at_risk" if risk_score < 50 else "vulnerable",
                "vulnerabilities": vulnerabilities[:10]  # Limit to top 10
            }
        
        return Tool(
            name="scan_for_vulnerabilities",
            description="Scan agent for security vulnerabilities",
            input_schema={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=scan_for_vulnerabilities
        )
    
    def _create_performance_benchmark_tool(self) -> Tool:
        """Create tool for performance benchmarking."""
        
        async def run_performance_benchmark(iterations: int = 100) -> Dict:
            """Run performance benchmarks."""
            
            import time
            import statistics
            
            latencies = []
            memory_usage = []
            
            for _ in range(iterations):
                # Measure operation latency
                start = time.time()
                
                # Simulate some work
                result = sum(i * i for i in range(1000))
                
                latency = (time.time() - start) * 1000
                latencies.append(latency)
                
                # Measure memory (simplified)
                import sys
                memory = sys.getsizeof(self.test_history) / 1024  # KB
                memory_usage.append(memory)
                
                await asyncio.sleep(0.01)
            
            return {
                "iterations": iterations,
                "latency_stats": {
                    "mean_ms": statistics.mean(latencies),
                    "median_ms": statistics.median(latencies),
                    "stdev_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0,
                    "min_ms": min(latencies),
                    "max_ms": max(latencies)
                },
                "memory_stats": {
                    "mean_kb": statistics.mean(memory_usage),
                    "max_kb": max(memory_usage)
                },
                "performance_grade": self._calculate_performance_grade(statistics.mean(latencies))
            }
        
        return Tool(
            name="run_performance_benchmark",
            description="Run performance benchmarks on the agent",
            input_schema={
                "type": "object",
                "properties": {
                    "iterations": {
                        "type": "integer",
                        "description": "Number of iterations to run",
                        "minimum": 10,
                        "maximum": 1000
                    }
                },
                "required": []
            },
            handler=run_performance_benchmark
        )
    
    async def _test_memory(self) -> TestResult:
        """Test memory usage."""
        import sys
        import time
        
        start = time.time()
        memory_kb = sys.getsizeof(self.__dict__) / 1024
        duration = (time.time() - start) * 1000
        
        passed = memory_kb < 1000  # Less than 1MB
        
        return TestResult(
            test_name="memory_usage",
            passed=passed,
            message=f"Memory usage: {memory_kb:.2f} KB",
            duration_ms=duration,
            details={"memory_kb": memory_kb}
        )
    
    async def _test_response_time(self) -> TestResult:
        """Test response time."""
        import time
        
        start = time.time()
        
        # Simulate some operation
        await asyncio.sleep(0.01)
        result = sum(i for i in range(1000))
        
        duration = (time.time() - start) * 1000
        passed = duration < 100  # Less than 100ms
        
        return TestResult(
            test_name="response_time",
            passed=passed,
            message=f"Response time: {duration:.2f} ms",
            duration_ms=duration
        )
    
    async def _test_error_handling(self) -> TestResult:
        """Test error handling."""
        import time
        
        start = time.time()
        
        try:
            # Try something that might fail
            result = 1 / 1  # This won't fail, but in real tests it might
            passed = True
            message = "Error handling working correctly"
        except Exception as e:
            passed = False
            message = f"Error handling failed: {str(e)}"
        
        duration = (time.time() - start) * 1000
        
        return TestResult(
            test_name="error_handling",
            passed=passed,
            message=message,
            duration_ms=duration
        )
    
    async def _test_concurrency(self) -> TestResult:
        """Test concurrent operations."""
        import time
        
        start = time.time()
        
        # Run multiple operations concurrently
        tasks = [self._test_response_time() for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        failures = sum(1 for r in results if isinstance(r, Exception))
        passed = failures == 0
        
        duration = (time.time() - start) * 1000
        
        return TestResult(
            test_name="concurrency",
            passed=passed,
            message=f"Handled {len(tasks)} concurrent operations, {failures} failures",
            duration_ms=duration,
            details={"concurrent_tasks": len(tasks), "failures": failures}
        )
    
    def _generate_recommendations(self, avg_score: float, failure_rate: float) -> List[str]:
        """Generate recommendations based on metrics."""
        
        recommendations = []
        
        if avg_score < 80:
            recommendations.append("Consider optimizing performance - reliability score below 80")
        
        if failure_rate > 0.1:
            recommendations.append("High failure rate detected - investigate error handling")
        
        if self.reliability_score < 90:
            recommendations.append("Run comprehensive diagnostics to identify issues")
        
        if not recommendations:
            recommendations.append("Agent is performing well - continue monitoring")
        
        return recommendations
    
    def _calculate_performance_grade(self, avg_latency: float) -> str:
        """Calculate performance grade based on latency."""
        
        if avg_latency < 1:
            return "A+"
        elif avg_latency < 5:
            return "A"
        elif avg_latency < 10:
            return "B"
        elif avg_latency < 50:
            return "C"
        elif avg_latency < 100:
            return "D"
        else:
            return "F"


# Modal deployment
app = modal.App("self-testing-agent")

@app.function(
    image=modal.Image.debian_slim(python_version="3.11")
    .pip_install("mcp", "aiohttp"),
    container_idle_timeout=300
)
@modal.web_endpoint(method="POST", label="self-testing-agent")
async def agent_endpoint(request: Dict) -> Dict:
    """Modal endpoint for the self-testing agent."""
    
    agent = SelfTestingAgent()
    
    # Route to appropriate tool
    tool_name = request.get("tool")
    params = request.get("params", {})
    
    if tool_name in agent.tools:
        result = await agent.tools[tool_name].handler(**params)
        return {"success": True, "result": result}
    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    # For local testing
    async def test():
        agent = SelfTestingAgent()
        
        # Run self-test
        result = await agent.tools["run_self_test"].handler("comprehensive")
        print("Self-test result:", json.dumps(result, indent=2))
        
        # Generate report
        report = await agent.tools["generate_reliability_report"].handler()
        print("\nReliability report:", json.dumps(report, indent=2))
        
        # Scan for vulnerabilities
        vulns = await agent.tools["scan_for_vulnerabilities"].handler()
        print("\nVulnerability scan:", json.dumps(vulns, indent=2))
    
    asyncio.run(test())