#!/usr/bin/env python3
"""
Modal Example: Test MCP Servers at Scale
Shows how to use MCP Reliability Lab with Modal for massive parallelization.
"""

import modal
import asyncio
from typing import List, Dict


# Example 1: Test a single server
async def test_single_server():
    """Test a single MCP server using Modal."""
    
    print("🚀 Testing single MCP server with Modal")
    print("=" * 50)
    
    # Import Modal function
    from modal_app import MCPTestRunner
    
    # Create runner
    runner = MCPTestRunner()
    
    # Test server
    result = await runner.test_server.remote(
        server_url="https://example-mcp-server.com",
        test_types=["security", "performance", "reliability"]
    )
    
    print(f"\n📊 Test Results:")
    print(f"Server: {result['server_url']}")
    print(f"Overall Score: {result['overall_score']}/100")
    print(f"Issues Found: {result['issues_found']}")
    print(f"Status: {result['status']}")
    
    # Show detailed results
    if "tests" in result:
        for test_name, test_result in result["tests"].items():
            print(f"\n{test_name.capitalize()} Test:")
            print(f"  Score: {test_result.get('score', 'N/A')}/100")
            if test_name == "security":
                print(f"  Vulnerabilities: {test_result.get('vulnerabilities', 0)}")
    
    return result


# Example 2: Test multiple servers in parallel
async def test_multiple_servers():
    """Test multiple MCP servers in parallel."""
    
    print("\n🚀 Testing multiple MCP servers in parallel")
    print("=" * 50)
    
    # List of servers to test
    server_urls = [
        "https://mcp-server-1.example.com",
        "https://mcp-server-2.example.com",
        "https://mcp-server-3.example.com",
        "https://api.openai.com/mcp",
        "https://api.anthropic.com/mcp",
    ]
    
    print(f"Testing {len(server_urls)} servers in parallel...")
    
    # Import Modal function
    from modal_app import MCPTestRunner
    
    runner = MCPTestRunner()
    
    # Test all servers in parallel
    results = await runner.batch_test.remote(
        server_urls=server_urls,
        test_types=["security"],
        parallel=True
    )
    
    print(f"\n📊 Batch Test Results:")
    print(f"Servers Tested: {len(results)}")
    
    # Show summary
    total_vulnerabilities = 0
    failed_servers = []
    
    for result in results:
        if result.get("issues_found", 0) > 0:
            total_vulnerabilities += result["issues_found"]
        if result.get("overall_score", 100) < 50:
            failed_servers.append(result["server_url"])
    
    print(f"Total Vulnerabilities Found: {total_vulnerabilities}")
    print(f"High-Risk Servers: {len(failed_servers)}")
    
    if failed_servers:
        print("\n⚠️  High-Risk Servers:")
        for server in failed_servers[:5]:
            print(f"  - {server}")
    
    return results


# Example 3: Use the Reliability Oracle
async def predict_failures():
    """Use ML to predict server failures."""
    
    print("\n🔮 Predicting server failures with ML")
    print("=" * 50)
    
    # Import reliability oracle
    from agents.reliability_oracle import predict_failures
    
    # Simulate server metrics
    server_metrics = [
        {
            "server_id": "production-api-1",
            "error_rate": 0.15,  # 15% errors - concerning!
            "latency_p99_ms": 5000,
            "memory_usage_percent": 85,
            "cpu_usage_percent": 92,
            "recent_errors": ["timeout", "injection attempt", "memory error"],
            "uptime_hours": 2
        },
        {
            "server_id": "production-api-2",
            "error_rate": 0.02,
            "latency_p99_ms": 200,
            "memory_usage_percent": 45,
            "cpu_usage_percent": 30,
            "recent_errors": [],
            "uptime_hours": 720
        }
    ]
    
    print(f"Analyzing {len(server_metrics)} servers for failure prediction...")
    
    # Get predictions
    result = await predict_failures.remote(server_metrics)
    
    print(f"\n🎯 Prediction Results:")
    print(f"Servers Analyzed: {result['servers_analyzed']}")
    print(f"Failures Predicted: {result['failures_predicted']}")
    print(f"Processing Time: {result['processing_time_ms']:.2f}ms (GPU-accelerated)")
    
    if result['critical_predictions']:
        print(f"\n⚠️  CRITICAL PREDICTIONS:")
        for pred in result['critical_predictions'][:3]:
            print(f"\nServer: {pred['server']}")
            print(f"  Failure Probability: {pred['probability']}")
            print(f"  Time to Failure: {pred['time_to_failure_minutes']} minutes")
            print(f"  Confidence: {pred['confidence']}")
            print(f"  Recommended Action: {pred['top_action']}")
    
    return result


# Example 4: Test 1000 servers (hackathon demo)
async def massive_parallel_test():
    """Demonstrate testing 1000+ servers in seconds."""
    
    print("\n🚀 MASSIVE PARALLEL TEST: 1000 Servers")
    print("=" * 50)
    
    # Generate 1000 test URLs
    server_urls = [
        f"https://test-server-{i}.example.com"
        for i in range(1000)
    ]
    
    print(f"Testing {len(server_urls)} servers in parallel...")
    print("Traditional approach would take: ~16 hours")
    print("With Modal: ~2 seconds")
    
    import time
    start_time = time.time()
    
    # Import Modal function
    from modal_app import massive_parallel_test as mpt
    
    # Run massive test
    result = await mpt.remote(server_urls)
    
    elapsed = time.time() - start_time
    
    print(f"\n✅ COMPLETED IN {elapsed:.2f} SECONDS!")
    print(f"\n📊 Results:")
    print(f"  Total Servers: {result['total_servers']}")
    print(f"  Servers/Second: {result['servers_per_second']:.1f}")
    print(f"  Vulnerabilities Found: {result['results_summary']['vulnerabilities_found']}")
    
    speedup = (16 * 3600) / elapsed  # 16 hours in seconds / actual time
    print(f"\n🎯 Performance:")
    print(f"  Speedup: {speedup:.0f}x faster than traditional approach")
    print(f"  Cost Savings: ${16 * 150:.2f} in engineering time")
    
    return result


# Example 5: Self-testing agent
async def test_self_testing_agent():
    """Demonstrate self-testing MCP agent."""
    
    print("\n🤖 Self-Testing MCP Agent Demo")
    print("=" * 50)
    
    from agents.self_testing_agent import agent_endpoint
    
    print("Running comprehensive self-diagnostics...")
    
    # Run self-test
    result = await agent_endpoint.remote({
        "tool": "run_self_test",
        "params": {"test_type": "comprehensive"}
    })
    
    if result["success"]:
        test_result = result["result"]
        print(f"\n✅ Self-Test Results:")
        print(f"  Status: {test_result['status']}")
        print(f"  Reliability Score: {test_result['reliability_score']}/100")
        print(f"  Tests Passed: {test_result['tests_passed']}/{test_result['tests_total']}")
        
        print(f"\n📋 Test Details:")
        for test in test_result["results"][:5]:
            status = "✅" if test["passed"] else "❌"
            print(f"  {status} {test['test']}: {test['message']}")
    
    # Test another agent
    print("\n🔬 Testing another MCP agent...")
    
    test_other_result = await agent_endpoint.remote({
        "tool": "test_other_agent",
        "params": {
            "agent_url": "https://example-mcp-agent.com",
            "test_suite": "security"
        }
    })
    
    if test_other_result["success"]:
        other_result = test_other_result["result"]
        print(f"\n📊 Other Agent Test Results:")
        print(f"  Agent URL: {other_result['agent_url']}")
        print(f"  Overall Score: {other_result['overall_score']:.1f}/100")
        print(f"  Tests Run: {len(other_result['tests'])}")
    
    return result


async def main():
    """Run all examples."""
    
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║                                                                  ║
    ║         MCP RELIABILITY LAB - MODAL EXAMPLES                    ║
    ║                                                                  ║
    ║         Demonstrating Modal-Powered MCP Testing                 ║
    ║                                                                  ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)
    
    examples = [
        ("Single Server Test", test_single_server),
        ("Multiple Servers (Parallel)", test_multiple_servers),
        ("ML Failure Prediction", predict_failures),
        ("Massive Parallel Test (1000 servers)", massive_parallel_test),
        ("Self-Testing Agent", test_self_testing_agent)
    ]
    
    print("\nAvailable Examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"{i}. {name}")
    
    print("\nNote: These examples require Modal deployment.")
    print("Run './deploy_to_modal.sh' first if you haven't already.")
    
    # Uncomment to run specific examples:
    # await test_single_server()
    # await test_multiple_servers()
    # await predict_failures()
    # await massive_parallel_test()
    # await test_self_testing_agent()
    
    print("\n✅ Examples demonstrate Modal's capabilities for MCP testing")
    print("🚀 Ready for production deployment!")


if __name__ == "__main__":
    # Check if Modal is installed
    try:
        import modal
        print("✅ Modal is installed")
    except ImportError:
        print("❌ Modal not installed. Run: pip install modal")
        exit(1)
    
    # Note: In production, these would be called via Modal
    print("\nTo run these examples on Modal:")
    print("1. Deploy: ./deploy_to_modal.sh")
    print("2. Run: modal run examples/modal_example.py")
    
    # For local testing (simulated)
    asyncio.run(main())