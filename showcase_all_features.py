#!/usr/bin/env python3
"""
Showcase All Features - MCP Reliability Lab
Demonstrates all the major improvements and new capabilities.
"""

import asyncio
import json
from pathlib import Path

# Import all our new tools
from test_servers import ServerTester
from mcp_protocol_validator import MCPProtocolValidator
from security_scanner import MCPSecurityScanner
from reliability_metrics import ReliabilityTester
from benchmarking.benchmark_runner import BenchmarkRunner
from benchmarking.workloads import StandardWorkloads
from config import SERVERS


async def main():
    """Demonstrate all features of the improved MCP Reliability Lab."""
    
    print("=" * 70)
    print(" MCP RELIABILITY LAB - COMPLETE FEATURE SHOWCASE")
    print(" Demonstrating all industry-first testing capabilities")
    print("=" * 70)
    
    # Server to test
    server_name = "filesystem"
    
    print(f"\nTesting server: {server_name}")
    print(f"Description: {SERVERS[server_name].get('description', 'N/A')}")
    
    # 1. Server Compatibility Test
    print("\n" + "─" * 70)
    print("1. SERVER COMPATIBILITY MATRIX (Industry First!)")
    print("─" * 70)
    
    tester = ServerTester()
    compatibility = await tester.test_server(server_name)
    
    if compatibility['status'] == 'working':
        print(f"✅ Server is compatible - {compatibility['tools_count']} tools available")
    else:
        print(f"❌ Compatibility issue: {compatibility['error']}")
    
    # 2. Protocol Validation
    print("\n" + "─" * 70)
    print("2. MCP PROTOCOL VALIDATOR (Industry First!)")
    print("─" * 70)
    
    validator = MCPProtocolValidator()
    protocol_report = await validator.validate_server(server_name, SERVERS[server_name])
    
    print(f"Protocol Compliance Score: {protocol_report.score}/100")
    print(f"Status: {'PASSED' if protocol_report.passed else 'FAILED'}")
    print(f"Compliance Areas: {protocol_report.checks_passed}/{protocol_report.checks_passed + protocol_report.checks_failed} passed")
    
    # 3. Security Vulnerability Scan
    print("\n" + "─" * 70)
    print("3. SECURITY VULNERABILITY SCANNER (Industry First!)")
    print("─" * 70)
    
    scanner = MCPSecurityScanner()
    security_report = await scanner.scan_server(server_name)
    
    print(f"Security Risk Score: {security_report.risk_score}/100")
    risk_level = (
        "CRITICAL" if security_report.risk_score >= 75 else
        "HIGH" if security_report.risk_score >= 50 else
        "MEDIUM" if security_report.risk_score >= 25 else
        "LOW" if security_report.risk_score >= 10 else
        "MINIMAL"
    )
    print(f"Risk Level: {risk_level}")
    print(f"Security Tests: {len(security_report.passed_tests)} passed, {len(security_report.failed_tests)} failed")
    
    # 4. Reliability Metrics
    print("\n" + "─" * 70)
    print("4. REAL RELIABILITY METRICS (Beyond Performance!)")
    print("─" * 70)
    
    print("Running 1-minute reliability test...")
    reliability_tester = ReliabilityTester()
    reliability = await reliability_tester.test_reliability(server_name, duration_minutes=1)
    
    print(f"Reliability Score: {reliability.reliability_score:.1f}/100")
    print(f"Availability: {reliability.availability:.2f}%")
    print(f"MTBF: {reliability.mtbf:.1f} seconds")
    print(f"Operation Success Rate: {reliability.operation_success_rate:.2f}%")
    
    # 5. Performance Benchmark
    print("\n" + "─" * 70)
    print("5. PERFORMANCE BENCHMARKING (Now Actually Works!)")
    print("─" * 70)
    
    runner = BenchmarkRunner()
    workload = StandardWorkloads.get_quick_benchmarks()["quick_mixed"]
    workload.duration_seconds = 5  # Very quick
    
    benchmark = await runner.run_benchmark(
        {"name": server_name, "type": server_name, "path": SERVERS[server_name].get("path", "/tmp")},
        workload
    )
    
    print(f"Throughput: {benchmark['operations_per_second']:.1f} ops/sec")
    print(f"Error Rate: {benchmark['error_rate']*100:.1f}%")
    print(f"P95 Latency: {benchmark['latencies']['p95']:.1f}ms")
    
    # 6. Overall Assessment
    print("\n" + "=" * 70)
    print("COMPREHENSIVE ASSESSMENT REPORT")
    print("=" * 70)
    
    # Calculate overall grade
    scores = {
        "Protocol Compliance": protocol_report.score,
        "Security": 100 - security_report.risk_score,
        "Reliability": reliability.reliability_score,
        "Performance": min(100, benchmark['operations_per_second'] / 3),  # Normalize to 100
        "Availability": reliability.availability
    }
    
    overall_score = sum(scores.values()) / len(scores)
    
    print("\nSCORES BY CATEGORY:")
    for category, score in scores.items():
        grade = (
            "A" if score >= 90 else
            "B" if score >= 80 else
            "C" if score >= 70 else
            "D" if score >= 60 else
            "F"
        )
        print(f"  {category:20} {score:5.1f}/100  Grade: {grade}")
    
    print(f"\nOVERALL SCORE: {overall_score:.1f}/100")
    
    overall_grade = (
        "A - Production Ready" if overall_score >= 90 else
        "B - Nearly Ready" if overall_score >= 80 else
        "C - Needs Work" if overall_score >= 70 else
        "D - Not Ready" if overall_score >= 60 else
        "F - Major Issues"
    )
    
    print(f"FINAL GRADE: {overall_grade}")
    
    # Save comprehensive report
    report = {
        "server": server_name,
        "overall_score": overall_score,
        "overall_grade": overall_grade,
        "scores": scores,
        "protocol": {
            "score": protocol_report.score,
            "passed": protocol_report.passed
        },
        "security": {
            "risk_score": security_report.risk_score,
            "findings": len(security_report.findings)
        },
        "reliability": {
            "score": reliability.reliability_score,
            "availability": reliability.availability,
            "mtbf": reliability.mtbf
        },
        "performance": {
            "throughput": benchmark['operations_per_second'],
            "error_rate": benchmark['error_rate'],
            "p95_latency": benchmark['latencies']['p95']
        }
    }
    
    with open(f"comprehensive_report_{server_name}.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nFull report saved to comprehensive_report_{server_name}.json")
    
    # Show unique value proposition
    print("\n" + "=" * 70)
    print("UNIQUE CAPABILITIES PROVIDED")
    print("=" * 70)
    print("✅ Protocol Validation - ONLY tool that validates MCP compliance")
    print("✅ Security Scanning - FIRST security testing for MCP servers")
    print("✅ Reliability Metrics - REAL MTBF/MTTR, not just performance")
    print("✅ Multi-Server Support - Test 10 different MCP server types")
    print("✅ Production Readiness - Complete assessment in one tool")
    
    print("\n" + "=" * 70)
    print("MCP Reliability Lab - The ONLY comprehensive MCP testing platform")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())