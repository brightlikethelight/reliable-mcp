#!/usr/bin/env python3
"""
MCP Reliability Lab CLI - Complete implementation with real functionality.
"""

import typer
import asyncio
import json
import sys
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.syntax import Syntax
from rich.live import Live
from rich.layout import Layout
from rich.prompt import Prompt, Confirm
import httpx
import websockets
from tabulate import tabulate
import pandas as pd
import yaml

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from mcp_reliability_lab.core.test_runner import TestRunner
from mcp_reliability_lab.core.benchmark_runner import BenchmarkRunner
from mcp_reliability_lab.core.server_manager import ServerManager
from mcp_reliability_lab.core.report_generator import ReportGenerator
from mcp_reliability_lab.utils.config import load_config, save_config
from mcp_reliability_lab.utils.auth import authenticate, get_stored_token

app = typer.Typer(
    name="mcp-reliability",
    help="MCP Reliability Lab CLI - Test and benchmark MCP servers",
    add_completion=False
)
console = Console()

# Global configuration
CONFIG_FILE = Path.home() / ".mcp-reliability" / "config.yaml"
API_BASE_URL = os.getenv("MCP_API_URL", "http://localhost:8000/api")
WS_BASE_URL = os.getenv("MCP_WS_URL", "ws://localhost:8000/ws")


def ensure_config():
    """Ensure configuration directory and file exist."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        default_config = {
            "api_url": API_BASE_URL,
            "ws_url": WS_BASE_URL,
            "default_timeout": 300,
            "output_format": "table"
        }
        save_config(CONFIG_FILE, default_config)
    return load_config(CONFIG_FILE)


def get_auth_headers():
    """Get authentication headers with JWT token."""
    token = get_stored_token()
    if not token:
        console.print("[red]Not authenticated. Please run 'mcp-reliability auth login' first.[/red]")
        raise typer.Exit(1)
    return {"Authorization": f"Bearer {token}"}


# Authentication commands
@app.command()
def login(
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True)
):
    """Login to MCP Reliability Lab."""
    with console.status("[bold green]Authenticating..."):
        try:
            response = httpx.post(
                f"{API_BASE_URL}/auth/login",
                json={"email": email, "password": password}
            )
            
            if response.status_code == 200:
                data = response.json()
                token = data["access_token"]
                
                # Store token
                token_file = Path.home() / ".mcp-reliability" / "token"
                token_file.parent.mkdir(parents=True, exist_ok=True)
                token_file.write_text(token)
                
                console.print("[green]✓[/green] Login successful!")
                console.print(f"Welcome, {data.get('username', email)}!")
            else:
                console.print(f"[red]Login failed: {response.text}[/red]")
                raise typer.Exit(1)
                
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)


@app.command()
def logout():
    """Logout from MCP Reliability Lab."""
    token_file = Path.home() / ".mcp-reliability" / "token"
    if token_file.exists():
        token_file.unlink()
        console.print("[green]✓[/green] Logged out successfully")
    else:
        console.print("[yellow]Not logged in[/yellow]")


# Test commands
@app.command()
def test(
    server: str = typer.Argument(..., help="MCP server name or ID to test"),
    suite: str = typer.Option("basic", "--suite", "-s", help="Test suite to run"),
    iterations: int = typer.Option(1, "--iterations", "-i", help="Number of iterations"),
    parallel: bool = typer.Option(False, "--parallel", "-p", help="Run tests in parallel"),
    timeout: int = typer.Option(300, "--timeout", "-t", help="Timeout in seconds"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json, csv, html"),
    save_to: Optional[Path] = typer.Option(None, "--save", help="Save results to file"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch test execution in real-time")
):
    """Run reliability tests on an MCP server."""
    headers = get_auth_headers()
    
    # Get server details
    with console.status(f"[bold green]Looking up server '{server}'..."):
        response = httpx.get(f"{API_BASE_URL}/servers", headers=headers)
        servers = response.json()
        
        server_info = None
        for s in servers:
            if s["name"] == server or s["id"] == server:
                server_info = s
                break
        
        if not server_info:
            console.print(f"[red]Server '{server}' not found[/red]")
            raise typer.Exit(1)
    
    console.print(f"[cyan]Testing server:[/cyan] {server_info['name']} ({server_info['transport_type']})")
    
    # Get test suite
    with console.status(f"[bold green]Loading test suite '{suite}'..."):
        response = httpx.get(f"{API_BASE_URL}/test-suites", headers=headers)
        suites = response.json()
        
        suite_info = None
        for s in suites:
            if s["name"] == suite:
                suite_info = s
                break
        
        if not suite_info:
            console.print(f"[red]Test suite '{suite}' not found[/red]")
            raise typer.Exit(1)
    
    console.print(f"[cyan]Test suite:[/cyan] {suite_info['name']} ({len(suite_info.get('test_cases', []))} tests)")
    
    # Start test run
    run_config = {
        "suite_id": suite_info["id"],
        "server_id": server_info["id"],
        "iterations": iterations,
        "parallel": parallel,
        "timeout": timeout
    }
    
    with console.status("[bold green]Starting test run..."):
        response = httpx.post(
            f"{API_BASE_URL}/test-runs",
            json=run_config,
            headers=headers
        )
        
        if response.status_code != 200:
            console.print(f"[red]Failed to start test: {response.text}[/red]")
            raise typer.Exit(1)
        
        test_run = response.json()
        run_id = test_run["id"]
    
    console.print(f"[green]✓[/green] Test run started: {run_id}")
    
    if watch:
        # Watch test execution in real-time
        asyncio.run(watch_test_execution(run_id, headers))
    else:
        # Poll for completion
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Running tests...", total=100)
            
            while True:
                response = httpx.get(f"{API_BASE_URL}/test-runs/{run_id}", headers=headers)
                status = response.json()
                
                progress.update(task, completed=status.get("progress", 0))
                
                if status["status"] in ["completed", "failed", "cancelled"]:
                    break
                
                asyncio.run(asyncio.sleep(1))
    
    # Get final results
    response = httpx.get(f"{API_BASE_URL}/test-runs/{run_id}/results", headers=headers)
    results = response.json()
    
    # Display results
    display_test_results(results, output)
    
    # Save if requested
    if save_to:
        save_results(results, save_to, output)
        console.print(f"[green]✓[/green] Results saved to {save_to}")


async def watch_test_execution(run_id: str, headers: dict):
    """Watch test execution in real-time via WebSocket."""
    token = headers["Authorization"].split(" ")[1]
    ws_url = f"{WS_BASE_URL}?token={token}"
    
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="progress", size=5),
        Layout(name="logs", size=15),
        Layout(name="metrics", size=8)
    )
    
    layout["header"].update(Panel(f"Test Run: {run_id}", title="MCP Reliability Lab"))
    
    async with websockets.connect(ws_url) as websocket:
        # Subscribe to test updates
        await websocket.send(json.dumps({
            "type": "subscribe",
            "channel": f"test:{run_id}"
        }))
        
        with Live(layout, console=console, refresh_per_second=4):
            async for message in websocket:
                data = json.loads(message)
                
                if data["type"] == "test_update":
                    # Update progress
                    progress_text = f"Status: {data['status']}\nProgress: {data['progress']}%"
                    layout["progress"].update(Panel(progress_text, title="Progress"))
                
                elif data["type"] == "log":
                    # Update logs
                    if not hasattr(watch_test_execution, "logs"):
                        watch_test_execution.logs = []
                    watch_test_execution.logs.append(f"[{data['level']}] {data['message']}")
                    log_text = "\n".join(watch_test_execution.logs[-20:])  # Show last 20 lines
                    layout["logs"].update(Panel(log_text, title="Logs"))
                
                elif data["type"] == "metrics":
                    # Update metrics
                    metrics_text = json.dumps(data.get("metrics", {}), indent=2)
                    layout["metrics"].update(Panel(metrics_text, title="Metrics"))
                
                # Check if test is complete
                if data.get("status") in ["completed", "failed", "cancelled"]:
                    break


def display_test_results(results: dict, format: str):
    """Display test results in specified format."""
    if format == "json":
        console.print_json(data=results)
    
    elif format == "table":
        # Summary table
        summary = Table(title="Test Results Summary")
        summary.add_column("Metric", style="cyan")
        summary.add_column("Value", style="magenta")
        
        summary.add_row("Total Tests", str(results["total_tests"]))
        summary.add_row("Passed", f"[green]{results['passed_tests']}[/green]")
        summary.add_row("Failed", f"[red]{results['failed_tests']}[/red]")
        summary.add_row("Skipped", f"[yellow]{results['skipped_tests']}[/yellow]")
        summary.add_row("Success Rate", f"{results['success_rate']:.1f}%")
        summary.add_row("Duration", f"{results['duration_seconds']:.2f}s")
        
        console.print(summary)
        
        # Detailed results table
        if results.get("test_results"):
            details = Table(title="Test Case Results")
            details.add_column("Test Case", style="cyan")
            details.add_column("Status", style="magenta")
            details.add_column("Duration (ms)", style="yellow")
            details.add_column("Error", style="red")
            
            for test in results["test_results"]:
                status_color = {
                    "passed": "[green]PASS[/green]",
                    "failed": "[red]FAIL[/red]",
                    "skipped": "[yellow]SKIP[/yellow]",
                    "error": "[red]ERROR[/red]"
                }.get(test["status"], test["status"])
                
                details.add_row(
                    test["name"],
                    status_color,
                    str(test.get("duration_ms", "-")),
                    test.get("error", "") or "-"
                )
            
            console.print(details)
    
    elif format == "csv":
        # Convert to CSV
        df = pd.DataFrame(results.get("test_results", []))
        console.print(df.to_csv(index=False))
    
    elif format == "html":
        # Generate HTML report
        html = generate_html_report(results)
        console.print(html)


# Benchmark commands
@app.command()
def benchmark(
    server: str = typer.Argument(..., help="MCP server to benchmark"),
    type: str = typer.Option("swe-bench", "--type", "-t", help="Benchmark type: swe-bench, performance, reliability"),
    dataset: str = typer.Option("lite", "--dataset", "-d", help="Dataset to use"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of tasks to run"),
    output: str = typer.Option("table", "--output", "-o", help="Output format"),
    compare_with: Optional[str] = typer.Option(None, "--compare", help="Compare with another server")
):
    """Run benchmarks on an MCP server."""
    headers = get_auth_headers()
    
    console.print(f"[bold cyan]Running {type} benchmark on {server}[/bold cyan]")
    
    # Create benchmark run
    benchmark_config = {
        "server": server,
        "type": type,
        "dataset": dataset,
        "limit": limit
    }
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        
        # Start benchmark
        task = progress.add_task("Initializing benchmark...", total=limit)
        
        response = httpx.post(
            f"{API_BASE_URL}/benchmarks/run",
            json=benchmark_config,
            headers=headers,
            timeout=None  # No timeout for long-running benchmarks
        )
        
        if response.status_code != 200:
            console.print(f"[red]Failed to start benchmark: {response.text}[/red]")
            raise typer.Exit(1)
        
        benchmark_id = response.json()["id"]
        
        # Poll for updates
        completed_tasks = 0
        while completed_tasks < limit:
            response = httpx.get(f"{API_BASE_URL}/benchmarks/{benchmark_id}/status", headers=headers)
            status = response.json()
            
            new_completed = status.get("completed_tasks", 0)
            if new_completed > completed_tasks:
                progress.update(task, completed=new_completed)
                completed_tasks = new_completed
            
            if status["status"] == "completed":
                break
            
            asyncio.run(asyncio.sleep(2))
    
    # Get results
    response = httpx.get(f"{API_BASE_URL}/benchmarks/{benchmark_id}/results", headers=headers)
    results = response.json()
    
    # Display results
    display_benchmark_results(results, output)
    
    # Compare if requested
    if compare_with:
        compare_benchmarks(server, compare_with, type, headers)


def display_benchmark_results(results: dict, format: str):
    """Display benchmark results."""
    if format == "json":
        console.print_json(data=results)
    
    elif format == "table":
        # Summary
        console.print(Panel(
            f"[bold]Score: {results['score']:.1f}/100[/bold]\n"
            f"Tasks: {results['completed_tasks']}/{results['total_tasks']}\n"
            f"Duration: {results['duration_seconds']:.2f}s",
            title="Benchmark Results"
        ))
        
        # Task details
        if results.get("tasks"):
            table = Table(title="Task Results")
            table.add_column("Task", style="cyan")
            table.add_column("Status", style="magenta")
            table.add_column("Score", style="yellow")
            table.add_column("Time (s)", style="green")
            
            for task in results["tasks"]:
                status = "[green]✓[/green]" if task["success"] else "[red]✗[/red]"
                table.add_row(
                    task["name"],
                    status,
                    f"{task.get('score', 0):.1f}",
                    f"{task.get('duration', 0):.2f}"
                )
            
            console.print(table)


# Server management commands
@app.command()
def servers(
    action: str = typer.Argument("list", help="Action: list, add, remove, start, stop"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Server name"),
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="Server executable path"),
    type: str = typer.Option("stdio", "--type", "-t", help="Transport type: stdio, http, websocket"),
    url: Optional[str] = typer.Option(None, "--url", "-u", help="Server URL (for HTTP/WebSocket)")
):
    """Manage MCP servers."""
    headers = get_auth_headers()
    
    if action == "list":
        response = httpx.get(f"{API_BASE_URL}/servers", headers=headers)
        servers = response.json()
        
        table = Table(title="MCP Servers")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("Type", style="yellow")
        table.add_column("Status", style="green")
        table.add_column("Uptime", style="blue")
        
        for server in servers:
            status_color = {
                "online": "[green]ONLINE[/green]",
                "offline": "[red]OFFLINE[/red]",
                "error": "[red]ERROR[/red]"
            }.get(server["status"], server["status"])
            
            table.add_row(
                server["id"][:8],
                server["name"],
                server["transport_type"],
                status_color,
                format_uptime(server.get("uptime_seconds", 0))
            )
        
        console.print(table)
    
    elif action == "add":
        if not name:
            name = Prompt.ask("Server name")
        
        server_config = {
            "name": name,
            "transport_type": type
        }
        
        if type == "stdio":
            if not path:
                path = Path(Prompt.ask("Server executable path"))
            server_config["server_path"] = str(path)
        else:
            if not url:
                url = Prompt.ask("Server URL")
            server_config["server_url"] = url
        
        response = httpx.post(
            f"{API_BASE_URL}/servers",
            json=server_config,
            headers=headers
        )
        
        if response.status_code == 200:
            console.print(f"[green]✓[/green] Server '{name}' added successfully")
        else:
            console.print(f"[red]Failed to add server: {response.text}[/red]")
    
    elif action == "remove":
        if not name:
            name = Prompt.ask("Server name to remove")
        
        if Confirm.ask(f"Remove server '{name}'?"):
            response = httpx.delete(f"{API_BASE_URL}/servers/{name}", headers=headers)
            
            if response.status_code == 200:
                console.print(f"[green]✓[/green] Server '{name}' removed")
            else:
                console.print(f"[red]Failed to remove server: {response.text}[/red]")
    
    elif action in ["start", "stop"]:
        if not name:
            name = Prompt.ask(f"Server name to {action}")
        
        response = httpx.post(
            f"{API_BASE_URL}/servers/{name}/{action}",
            headers=headers
        )
        
        if response.status_code == 200:
            console.print(f"[green]✓[/green] Server '{name}' {action}ed")
        else:
            console.print(f"[red]Failed to {action} server: {response.text}[/red]")


# Report generation commands
@app.command()
def report(
    type: str = typer.Option("summary", "--type", "-t", help="Report type: summary, detailed, compliance"),
    period: str = typer.Option("week", "--period", "-p", help="Time period: day, week, month"),
    format: str = typer.Option("pdf", "--format", "-f", help="Output format: pdf, html, markdown"),
    output: Path = typer.Option(Path("report.pdf"), "--output", "-o", help="Output file")
):
    """Generate reports from test results."""
    headers = get_auth_headers()
    
    console.print(f"[bold cyan]Generating {type} report for last {period}...[/bold cyan]")
    
    with console.status("[bold green]Generating report..."):
        response = httpx.post(
            f"{API_BASE_URL}/reports/generate",
            json={
                "type": type,
                "period": period,
                "format": format
            },
            headers=headers,
            timeout=60
        )
        
        if response.status_code != 200:
            console.print(f"[red]Failed to generate report: {response.text}[/red]")
            raise typer.Exit(1)
    
    # Save report
    output.write_bytes(response.content)
    console.print(f"[green]✓[/green] Report saved to {output}")
    
    # Open report if PDF
    if format == "pdf" and sys.platform == "darwin":
        os.system(f"open {output}")
    elif format == "html":
        import webbrowser
        webbrowser.open(f"file://{output.absolute()}")


# Utility functions
def format_uptime(seconds: int) -> str:
    """Format uptime in human-readable format."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}d {hours}h"


def generate_html_report(results: dict) -> str:
    """Generate HTML report from results."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>MCP Reliability Test Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1 {{ color: #333; }}
            .summary {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
            .passed {{ color: green; }}
            .failed {{ color: red; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background: #4CAF50; color: white; }}
        </style>
    </head>
    <body>
        <h1>MCP Reliability Test Report</h1>
        <div class="summary">
            <h2>Summary</h2>
            <p>Total Tests: {results['total_tests']}</p>
            <p class="passed">Passed: {results['passed_tests']}</p>
            <p class="failed">Failed: {results['failed_tests']}</p>
            <p>Success Rate: {results['success_rate']:.1f}%</p>
            <p>Duration: {results['duration_seconds']:.2f} seconds</p>
        </div>
        <h2>Test Results</h2>
        <table>
            <tr>
                <th>Test Case</th>
                <th>Status</th>
                <th>Duration (ms)</th>
                <th>Error</th>
            </tr>
    """
    
    for test in results.get("test_results", []):
        status_class = "passed" if test["status"] == "passed" else "failed"
        html += f"""
            <tr>
                <td>{test['name']}</td>
                <td class="{status_class}">{test['status'].upper()}</td>
                <td>{test.get('duration_ms', '-')}</td>
                <td>{test.get('error', '-')}</td>
            </tr>
        """
    
    html += """
        </table>
    </body>
    </html>
    """
    
    return html


def save_results(results: dict, path: Path, format: str):
    """Save results to file in specified format."""
    if format == "json":
        path.write_text(json.dumps(results, indent=2))
    elif format == "csv":
        df = pd.DataFrame(results.get("test_results", []))
        df.to_csv(path, index=False)
    elif format == "html":
        html = generate_html_report(results)
        path.write_text(html)
    else:
        # Default to JSON
        path.write_text(json.dumps(results, indent=2))


def compare_benchmarks(server1: str, server2: str, type: str, headers: dict):
    """Compare benchmark results between two servers."""
    console.print(f"\n[bold cyan]Comparing {server1} vs {server2}[/bold cyan]")
    
    # Get results for both servers
    response1 = httpx.get(f"{API_BASE_URL}/benchmarks/latest/{server1}?type={type}", headers=headers)
    response2 = httpx.get(f"{API_BASE_URL}/benchmarks/latest/{server2}?type={type}", headers=headers)
    
    if response1.status_code != 200 or response2.status_code != 200:
        console.print("[red]Failed to fetch comparison data[/red]")
        return
    
    results1 = response1.json()
    results2 = response2.json()
    
    # Create comparison table
    table = Table(title="Benchmark Comparison")
    table.add_column("Metric", style="cyan")
    table.add_column(server1, style="magenta")
    table.add_column(server2, style="yellow")
    table.add_column("Difference", style="green")
    
    metrics = [
        ("Overall Score", "score"),
        ("Success Rate", "success_rate"),
        ("Avg Response Time", "avg_response_time"),
        ("Throughput", "throughput")
    ]
    
    for label, key in metrics:
        val1 = results1.get(key, 0)
        val2 = results2.get(key, 0)
        
        if val1 and val2:
            diff = ((val2 - val1) / val1) * 100
            diff_str = f"{diff:+.1f}%"
            if diff > 0:
                diff_str = f"[green]{diff_str}[/green]"
            else:
                diff_str = f"[red]{diff_str}[/red]"
        else:
            diff_str = "-"
        
        table.add_row(
            label,
            f"{val1:.2f}",
            f"{val2:.2f}",
            diff_str
        )
    
    console.print(table)


# Version and help commands
@app.command()
def version():
    """Show version information."""
    console.print("[bold]MCP Reliability Lab CLI[/bold]")
    console.print("Version: 1.0.0")
    console.print("Python: " + sys.version.split()[0])


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
    set: Optional[str] = typer.Option(None, "--set", help="Set config value (key=value)"),
    api_url: Optional[str] = typer.Option(None, "--api-url", help="Set API URL"),
    ws_url: Optional[str] = typer.Option(None, "--ws-url", help="Set WebSocket URL")
):
    """Manage CLI configuration."""
    config = ensure_config()
    
    if show:
        console.print(Panel(yaml.dump(config, default_flow_style=False), title="Configuration"))
    
    if set:
        key, value = set.split("=", 1)
        config[key] = value
        save_config(CONFIG_FILE, config)
        console.print(f"[green]✓[/green] Set {key} = {value}")
    
    if api_url:
        config["api_url"] = api_url
        save_config(CONFIG_FILE, config)
        console.print(f"[green]✓[/green] API URL updated")
    
    if ws_url:
        config["ws_url"] = ws_url
        save_config(CONFIG_FILE, config)
        console.print(f"[green]✓[/green] WebSocket URL updated")


if __name__ == "__main__":
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)