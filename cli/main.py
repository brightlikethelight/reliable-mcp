"""Main CLI application for MCP reliability testing."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import track
from rich import print as rprint

from ..core.config import (
    MCPServerConfig, StdioTransportConfig, ServerType, 
    MCPRetryConfig, MCPObservabilityConfig
)
from ..core.wrapper import MCPServerWrapper
from ..observability import setup_telemetry


app = typer.Typer(
    name="mcp-lab",
    help="MCP Agent Reliability Lab - Comprehensive testing framework for MCP servers"
)
console = Console()


@app.command()
def test_server(
    server_path: str = typer.Argument(..., help="Path to MCP server executable"),
    server_type: str = typer.Option("python", help="Server type (python/typescript)"),
    max_attempts: int = typer.Option(3, help="Maximum retry attempts"),
    timeout: float = typer.Option(60.0, help="Call timeout in seconds"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    enable_tracing: bool = typer.Option(False, help="Enable OpenTelemetry tracing"),
    output_file: Optional[str] = typer.Option(None, help="Output file for results")
):
    """Test an MCP server with comprehensive reliability testing."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
        
    asyncio.run(_test_server_async(
        server_path, server_type, max_attempts, timeout, 
        enable_tracing, output_file
    ))


async def _test_server_async(
    server_path: str,
    server_type: str,
    max_attempts: int,
    timeout: float,
    enable_tracing: bool,
    output_file: Optional[str]
):
    """Async implementation of server testing."""
    # Setup telemetry if requested
    if enable_tracing:
        setup_telemetry(service_name="mcp-reliability-test")
        rprint("✅ OpenTelemetry tracing enabled")
    
    # Configure wrapper
    config = MCPServerConfig(
        server_type=ServerType(server_type),
        transport_config=StdioTransportConfig(
            command=server_path.split() if isinstance(server_path, str) else [server_path]
        ),
        retry_config=MCPRetryConfig(max_attempts=max_attempts),
        observability_config=MCPObservabilityConfig(
            enable_tracing=enable_tracing,
            enable_metrics=enable_tracing
        )
    )
    
    console.print(f"🧪 Testing MCP server: {server_path}")
    console.print(f"📋 Configuration:")
    console.print(f"   - Server type: {server_type}")
    console.print(f"   - Max attempts: {max_attempts}")
    console.print(f"   - Timeout: {timeout}s")
    console.print(f"   - Tracing: {'enabled' if enable_tracing else 'disabled'}")
    console.print()
    
    results = []
    
    async with MCPServerWrapper(config) as wrapper:
        # Basic connectivity test
        console.print("🔌 Testing connectivity...")
        health = await wrapper.health_check()
        
        if health["status"] == "healthy":
            console.print("✅ Connection successful")
            results.append({"test": "connectivity", "status": "passed"})
        else:
            console.print(f"❌ Connection failed: {health.get('error', 'Unknown error')}")
            results.append({"test": "connectivity", "status": "failed", "error": health.get('error')})
            return
        
        # List available tools
        console.print("🛠️  Discovering tools...")
        try:
            tools = await wrapper.list_tools()
            console.print(f"✅ Found {len(tools)} tools")
            
            # Display tools table
            table = Table(title="Available Tools")
            table.add_column("Name", style="cyan")
            table.add_column("Description", style="green")
            
            for tool in tools:
                table.add_row(tool["name"], tool.get("description", "No description"))
            
            console.print(table)
            results.append({"test": "tool_discovery", "status": "passed", "tool_count": len(tools)})
            
        except Exception as e:
            console.print(f"❌ Tool discovery failed: {e}")
            results.append({"test": "tool_discovery", "status": "failed", "error": str(e)})
            return
        
        # Test each tool
        console.print("\n🎯 Testing individual tools...")
        for tool in track(tools, description="Testing tools..."):
            tool_name = tool["name"]
            
            try:
                # Generate appropriate test parameters based on tool
                test_params = _get_test_parameters(tool_name)
                
                result = await wrapper.call_tool(tool_name, test_params)
                
                if not result.get("isError", True):
                    console.print(f"✅ {tool_name}: Success")
                    results.append({"test": f"tool_{tool_name}", "status": "passed"})
                else:
                    console.print(f"⚠️  {tool_name}: Returned error")
                    results.append({"test": f"tool_{tool_name}", "status": "warning", "message": "Tool returned error"})
                    
            except Exception as e:
                console.print(f"❌ {tool_name}: Exception - {e}")
                results.append({"test": f"tool_{tool_name}", "status": "failed", "error": str(e)})
        
        # I/O Capture test
        console.print("\n📝 Testing I/O capture...")
        captured = wrapper.get_captured_io()
        if captured:
            console.print(f"✅ Captured {len(captured)} interactions")
            results.append({"test": "io_capture", "status": "passed", "interaction_count": len(captured)})
        else:
            console.print("⚠️  No I/O captured")
            results.append({"test": "io_capture", "status": "warning"})
    
    # Summary
    console.print("\n📊 Test Summary")
    
    passed = sum(1 for r in results if r["status"] == "passed")
    failed = sum(1 for r in results if r["status"] == "failed")
    warnings = sum(1 for r in results if r["status"] == "warning")
    
    summary_table = Table()
    summary_table.add_column("Status", style="bold")
    summary_table.add_column("Count", justify="right")
    
    summary_table.add_row("✅ Passed", str(passed), style="green")
    summary_table.add_row("❌ Failed", str(failed), style="red")
    summary_table.add_row("⚠️  Warnings", str(warnings), style="yellow")
    
    console.print(summary_table)
    
    # Write results to file if requested
    if output_file:
        import json
        with open(output_file, 'w') as f:
            json.dump({
                "server_path": server_path,
                "server_type": server_type,
                "config": config.model_dump(),
                "results": results,
                "summary": {"passed": passed, "failed": failed, "warnings": warnings}
            }, f, indent=2)
        console.print(f"📄 Results written to {output_file}")


def _get_test_parameters(tool_name: str) -> dict:
    """Generate appropriate test parameters for a tool."""
    if tool_name == "calculator":
        return {"operation": "add", "a": 2, "b": 3}
    elif tool_name == "weather":
        return {"location": "London", "days": 1}
    elif tool_name == "file_ops":
        return {"operation": "list"}
    elif tool_name == "error_simulator":
        return {"error_type": "random", "delay": 0.1}
    else:
        return {}


@app.command()
def benchmark(
    server_path: str = typer.Argument(..., help="Path to MCP server executable"),
    duration: int = typer.Option(60, help="Test duration in seconds"),
    concurrent: int = typer.Option(5, help="Number of concurrent requests"),
    tool_name: str = typer.Option("calculator", help="Tool to benchmark")
):
    """Benchmark MCP server performance."""
    asyncio.run(_benchmark_async(server_path, duration, concurrent, tool_name))


async def _benchmark_async(server_path: str, duration: int, concurrent: int, tool_name: str):
    """Async implementation of benchmarking."""
    console.print(f"🏃‍♂️ Benchmarking {server_path}")
    console.print(f"Duration: {duration}s, Concurrent: {concurrent}, Tool: {tool_name}")
    
    config = MCPServerConfig(
        server_type=ServerType.PYTHON,
        transport_config=StdioTransportConfig(
            command=server_path.split()
        )
    )
    
    results = []
    start_time = asyncio.get_event_loop().time()
    end_time = start_time + duration
    
    async def worker():
        """Benchmark worker."""
        count = 0
        errors = 0
        
        async with MCPServerWrapper(config) as wrapper:
            while asyncio.get_event_loop().time() < end_time:
                try:
                    params = _get_test_parameters(tool_name)
                    await wrapper.call_tool(tool_name, params)
                    count += 1
                except Exception:
                    errors += 1
                    
        return {"requests": count, "errors": errors}
    
    # Run concurrent workers
    console.print("🔥 Running benchmark...")
    with console.status("Benchmarking..."):
        worker_results = await asyncio.gather(*[worker() for _ in range(concurrent)])
    
    # Calculate statistics
    total_requests = sum(w["requests"] for w in worker_results)
    total_errors = sum(w["errors"] for w in worker_results)
    rps = total_requests / duration
    error_rate = total_errors / (total_requests + total_errors) if (total_requests + total_errors) > 0 else 0
    
    # Display results
    console.print(f"\n📈 Benchmark Results")
    console.print(f"Total requests: {total_requests}")
    console.print(f"Requests per second: {rps:.2f}")
    console.print(f"Error rate: {error_rate:.2%}")
    console.print(f"Success rate: {(1-error_rate):.2%}")


@app.command()
def property_test(
    server_path: str = typer.Argument(..., help="Path to MCP server executable"),
    examples: int = typer.Option(100, help="Number of examples to generate"),
    max_time: int = typer.Option(300, help="Maximum test time in seconds")
):
    """Run property-based tests using Hypothesis."""
    try:
        from hypothesis import settings, given
        import hypothesis.strategies as st
    except ImportError:
        console.print("❌ Hypothesis not installed. Install with: pip install hypothesis")
        sys.exit(1)
    
    console.print(f"🔬 Running property-based tests on {server_path}")
    console.print(f"Examples: {examples}, Max time: {max_time}s")
    console.print("⚠️  Property testing implementation would require integration with Hypothesis")
    
    # This would need actual integration with the property test framework
    console.print("🚧 Property testing feature coming soon!")


@app.command()
def chaos(
    server_path: str = typer.Argument(..., help="Path to MCP server executable"),
    experiment: str = typer.Option("network_delay", help="Chaos experiment type"),
    duration: int = typer.Option(60, help="Experiment duration in seconds")
):
    """Run chaos engineering experiments."""
    console.print(f"🌪️  Running chaos experiment: {experiment}")
    console.print(f"Target: {server_path}, Duration: {duration}s")
    console.print("🚧 Chaos engineering features coming soon!")


@app.command()
def dashboard(
    port: int = typer.Option(8080, help="Port to run dashboard on"),
    host: str = typer.Option("localhost", help="Host to bind to")
):
    """Launch the real-time monitoring dashboard."""
    console.print(f"🚀 Starting dashboard on http://{host}:{port}")
    console.print("🚧 Dashboard feature coming soon!")


if __name__ == "__main__":
    app()