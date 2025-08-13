#!/usr/bin/env python3
"""
Simple Web UI for MCP Reliability Lab.
Uses FastAPI + HTMX for a clean, functional interface.
"""

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from contextlib import asynccontextmanager
import json
import asyncio
from datetime import datetime
from pathlib import Path
import sys

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "services"))
sys.path.insert(0, str(Path(__file__).parent / "benchmarking"))

# Import configuration
from config import DATABASES, API_CONFIG

# Import our working components
from services.test_runner_service import TestRunnerService
from services.metrics_service import MetricsService
from scientific_test_runner_improved import ImprovedScientificTestRunner
from benchmarking.benchmark_runner import BenchmarkRunner
from benchmarking.leaderboard import Leaderboard
from benchmarking.workloads import StandardWorkloads


# Initialize services
test_runner = TestRunnerService()
metrics = MetricsService(DATABASES['web_metrics'])
scientific = ImprovedScientificTestRunner()
benchmark_runner = BenchmarkRunner(DATABASES['benchmarks'])
leaderboard = Leaderboard(DATABASES['leaderboard'])

# Create app
app = FastAPI(title="MCP Reliability Lab", version="1.0.0")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Mount static files (will create later)
static_dir = Path("static")
if not static_dir.exists():
    static_dir.mkdir()
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with overview stats."""
    
    # Get recent test results
    try:
        recent_tests = test_runner.get_recent_tests(limit=5)
    except:
        recent_tests = []
    
    # Get summary statistics
    try:
        stats = metrics.get_summary_stats()
    except:
        stats = {
            "total_tests": 0,
            "avg_reliability": 0,
            "servers_tested": 0,
            "success_rate": 0
        }
    
    # Get leaderboard top 3
    try:
        top_servers = leaderboard.get_server_rankings()[:3]
    except:
        top_servers = []
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "recent_tests": recent_tests,
        "stats": stats,
        "top_servers": top_servers
    })


@app.get("/test", response_class=HTMLResponse)
async def test_page(request: Request):
    """Test execution page."""
    
    # Get available workloads
    workloads = StandardWorkloads.get_all()
    workload_names = list(workloads.keys())
    
    return templates.TemplateResponse("test.html", {
        "request": request,
        "workloads": workload_names
    })


@app.post("/run-test", response_class=HTMLResponse)
async def run_test(
    request: Request,
    server_type: str = Form(...),
    test_type: str = Form(...),
    workload: str = Form(None)
):
    """Run test and return results via HTMX."""
    
    server_config = {
        "name": server_type,
        "type": server_type,
        "path": "/private/tmp"
    }
    
    try:
        if test_type == "basic":
            # Run basic reliability test
            test_config = {
                "name": f"Basic Test - {server_type}",
                "tests": [
                    {"name": "write", "tool": "write_file", "args": {"path": "/private/tmp/test.txt", "content": "test"}},
                    {"name": "read", "tool": "read_text_file", "args": {"path": "/private/tmp/test.txt"}},
                    {"name": "list", "tool": "list_directory", "args": {"path": "/private/tmp"}}
                ]
            }
            result = await test_runner.run_test(test_config)
            
            # Format results
            results = {
                "type": "Basic Test",
                "score": result.get("reliability_score", 0),
                "tests_passed": result.get("passed", 0),
                "total_tests": result.get("total", 0),
                "avg_latency": result.get("avg_duration_ms", 0),
                "status": "success" if result.get("passed") == result.get("total") else "partial",
                "details": result
            }
            
        elif test_type == "scientific":
            # Run scientific test suite (simplified for web)
            result = await scientific.run_scientific_suite(server_config)
            
            # Extract key metrics
            scientific_score = result.get("scientific_score", {})
            results = {
                "type": "Scientific Suite",
                "score": scientific_score.get("overall_score", 0),
                "grade": scientific_score.get("grade", "F"),
                "breakdown": scientific_score.get("breakdown", {}),
                "recommendation": scientific_score.get("recommendation", "Unknown"),
                "status": "success",
                "details": result
            }
            
        elif test_type == "benchmark":
            # Run benchmark test
            if not workload:
                workload = "real_world_mix"
            
            workloads = StandardWorkloads.get_all()
            selected_workload = workloads.get(workload)
            
            if not selected_workload:
                raise HTTPException(status_code=400, detail="Invalid workload")
            
            # Use shorter duration for web UI
            selected_workload.duration_seconds = 10
            selected_workload.warmup_seconds = 2
            
            result = await benchmark_runner.run_benchmark(server_config, selected_workload)
            
            # Add to leaderboard
            score = leaderboard.add_benchmark_result(
                server_type,
                selected_workload.name,
                result
            )
            
            results = {
                "type": f"Benchmark - {selected_workload.name}",
                "score": score,
                "throughput": result.get("operations_per_second", 0),
                "p95_latency": result.get("latencies", {}).get("p95", 0),
                "consistency": result.get("latencies", {}).get("consistency", 0),
                "error_rate": result.get("error_rate", 0),
                "status": "success",
                "details": result
            }
        else:
            raise HTTPException(status_code=400, detail="Invalid test type")
        
    except Exception as e:
        results = {
            "type": test_type,
            "score": 0,
            "status": "error",
            "error": str(e)
        }
    
    # Return partial HTML for HTMX
    return templates.TemplateResponse("partials/test_results.html", {
        "request": request,
        "results": results
    })


@app.get("/metrics", response_class=HTMLResponse)
async def metrics_page(request: Request):
    """Metrics dashboard page."""
    
    # Get metrics data
    try:
        metrics_24h = metrics.get_metrics_summary(hours=24)
        metrics_1h = metrics.get_metrics_summary(hours=1)
        per_tool = metrics.get_per_tool_metrics()
    except:
        metrics_24h = {"operations": 0, "success_rate": 0, "avg_duration_ms": 0}
        metrics_1h = {"operations": 0, "success_rate": 0, "avg_duration_ms": 0}
        per_tool = []
    
    # Prepare chart data
    chart_data = {
        "labels": [tool["tool_name"] for tool in per_tool[:10]],
        "operations": [tool["count"] for tool in per_tool[:10]],
        "latencies": [tool["avg_duration_ms"] for tool in per_tool[:10]]
    }
    
    return templates.TemplateResponse("metrics.html", {
        "request": request,
        "metrics_24h": metrics_24h,
        "metrics_1h": metrics_1h,
        "per_tool": per_tool[:10],
        "chart_data": json.dumps(chart_data)
    })


@app.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard_page(request: Request):
    """Leaderboard page."""
    
    # Get leaderboard data
    overall_rankings = leaderboard.get_server_rankings()
    recent_entries = leaderboard.get_leaderboard(limit=20)
    workload_bests = leaderboard.get_workload_bests()
    
    return templates.TemplateResponse("leaderboard.html", {
        "request": request,
        "overall_rankings": overall_rankings,
        "recent_entries": recent_entries,
        "workload_bests": workload_bests
    })


@app.get("/api/stats", response_class=JSONResponse)
async def api_stats():
    """API endpoint for live stats."""
    
    try:
        stats = metrics.get_summary_stats()
        return {
            "total_tests": stats.get("total_tests", 0),
            "avg_reliability": stats.get("avg_reliability", 0),
            "servers_tested": stats.get("servers_tested", 0),
            "last_update": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    print("Starting MCP Reliability Lab Web UI...")
    print("Open http://localhost:8000 in your browser")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)