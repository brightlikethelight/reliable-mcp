#!/usr/bin/env python3
"""
Run All Reality Tests

This script runs all the reality tests in sequence and provides a comprehensive
report of what actually works in the MCP Reliability Lab.
"""

import sys
import subprocess
import time
from pathlib import Path
from typing import List, Tuple, Dict, Any

def run_test(test_file: Path) -> Tuple[str, bool, str, float]:
    """Run a single test file and return results."""
    test_name = test_file.stem.replace('test_', '').replace('_', ' ').title()
    
    print(f"\n{'='*60}")
    print(f"RUNNING: {test_name}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            [sys.executable, str(test_file)],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout per test
        )
        
        duration = time.time() - start_time
        
        # Print the output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        success = result.returncode == 0
        output = result.stdout + ("\nSTDERR:\n" + result.stderr if result.stderr else "")
        
        return test_name, success, output, duration
        
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        return test_name, False, "TEST TIMED OUT", duration
    except Exception as e:
        duration = time.time() - start_time
        return test_name, False, f"EXECUTION ERROR: {e}", duration

def analyze_output(output: str) -> Dict[str, Any]:
    """Analyze test output for detailed results."""
    lines = output.split('\n')
    
    analysis = {
        'passed_items': [],
        'failed_items': [],
        'warnings': [],
        'components_working': [],
        'components_broken': []
    }
    
    for line in lines:
        line = line.strip()
        if line.startswith('✓'):
            analysis['passed_items'].append(line[2:])
        elif line.startswith('✗'):
            analysis['failed_items'].append(line[2:])
        elif line.startswith('!'):
            analysis['warnings'].append(line[2:])
        elif 'working' in line.lower() or 'functional' in line.lower():
            if '✓' in line:
                analysis['components_working'].append(line)
        elif 'failed' in line.lower() or 'broken' in line.lower():
            if '✗' in line:
                analysis['components_broken'].append(line)
    
    return analysis

def generate_report(results: List[Tuple[str, bool, str, float]]) -> None:
    """Generate a comprehensive report."""
    print(f"\n{'#'*80}")
    print("MCP RELIABILITY LAB - REALITY CHECK REPORT")
    print(f"{'#'*80}")
    
    total_tests = len(results)
    passed_tests = sum(1 for _, success, _, _ in results if success)
    total_time = sum(duration for _, _, _, duration in results)
    
    print(f"\n📊 OVERALL RESULTS:")
    print(f"   Tests Run: {total_tests}")
    print(f"   Tests Passed: {passed_tests}")
    print(f"   Tests Failed: {total_tests - passed_tests}")
    print(f"   Success Rate: {passed_tests/total_tests*100:.1f}%")
    print(f"   Total Time: {total_time:.1f}s")
    
    print(f"\n📋 TEST RESULTS:")
    for test_name, success, output, duration in results:
        status = "PASS" if success else "FAIL"
        print(f"   {test_name:<25} {status:<6} ({duration:.1f}s)")
    
    # Detailed analysis
    print(f"\n🔍 DETAILED ANALYSIS:")
    
    all_passed = []
    all_failed = []
    all_warnings = []
    working_components = set()
    broken_components = set()
    
    for test_name, success, output, _ in results:
        analysis = analyze_output(output)
        
        if analysis['passed_items']:
            print(f"\n   {test_name} - Working Features:")
            for item in analysis['passed_items'][:5]:  # Show first 5
                print(f"     ✓ {item}")
                all_passed.append(f"{test_name}: {item}")
            if len(analysis['passed_items']) > 5:
                print(f"     ... and {len(analysis['passed_items']) - 5} more")
        
        if analysis['failed_items']:
            print(f"\n   {test_name} - Issues:")
            for item in analysis['failed_items'][:3]:  # Show first 3
                print(f"     ✗ {item}")
                all_failed.append(f"{test_name}: {item}")
            if len(analysis['failed_items']) > 3:
                print(f"     ... and {len(analysis['failed_items']) - 3} more")
        
        if analysis['warnings']:
            for warning in analysis['warnings']:
                all_warnings.append(f"{test_name}: {warning}")
        
        working_components.update(analysis['components_working'])
        broken_components.update(analysis['components_broken'])
    
    # Component summary
    print(f"\n🧩 COMPONENT STATUS:")
    
    components = {
        "Configuration System": any("config" in str(r).lower() for r in results),
        "STDIO Transport": any("stdio" in str(r).lower() for r in results),
        "MCP Wrapper": any("wrapper" in str(r).lower() for r in results),
        "Sandbox Manager": any("sandbox" in str(r).lower() for r in results),
        "Chaos Engineering": any("chaos" in str(r).lower() for r in results)
    }
    
    for component, tested in components.items():
        if tested:
            # Check if the test passed
            component_test = next((r for r in results if component.lower().replace(" ", "") in r[0].lower().replace(" ", "")), None)
            if component_test:
                status = "✅ WORKING" if component_test[1] else "❌ BROKEN"
            else:
                status = "❓ TESTED"
        else:
            status = "⚪ NOT TESTED"
        
        print(f"   {component:<20} {status}")
    
    print(f"\n💡 KEY FINDINGS:")
    
    # Determine what definitely works
    definitely_working = []
    if any("config" in r[0].lower() and r[1] for r in results):
        definitely_working.append("Configuration models and validation")
    
    if any("stdio" in r[0].lower() and r[1] for r in results):
        definitely_working.append("STDIO transport with subprocess communication")
    
    if any("wrapper" in r[0].lower() and r[1] for r in results):
        definitely_working.append("High-level MCP wrapper interface")
    
    # Determine what needs work
    needs_work = []
    if any("sandbox" in r[0].lower() and not r[1] for r in results):
        needs_work.append("Sandbox providers (Modal, Docker, E2B not implemented)")
    
    if any("chaos" in r[0].lower() for r in results):
        chaos_result = next(r for r in results if "chaos" in r[0].lower())
        if not chaos_result[1]:
            needs_work.append("Chaos engineering execution (config works)")
    
    print(f"\n   ✅ DEFINITELY WORKING:")
    for item in definitely_working:
        print(f"     • {item}")
    
    print(f"\n   ⚠️  NEEDS WORK:")
    for item in needs_work:
        print(f"     • {item}")
    
    if all_warnings:
        print(f"\n   ⚡ WARNINGS:")
        for warning in all_warnings[:5]:  # Show first 5 warnings
            print(f"     • {warning}")
    
    # Verdict
    print(f"\n🎯 VERDICT:")
    
    if passed_tests >= total_tests * 0.8:
        verdict = "MCP Reliability Lab has a SOLID FOUNDATION"
        details = [
            "Core components are functional",
            "Configuration system works well", 
            "Basic MCP communication works",
            "Ready for integration with external services"
        ]
    elif passed_tests >= total_tests * 0.6:
        verdict = "MCP Reliability Lab is PARTIALLY FUNCTIONAL"
        details = [
            "Core concepts are implemented",
            "Some components need refinement",
            "Good foundation but needs more work"
        ]
    else:
        verdict = "MCP Reliability Lab NEEDS SIGNIFICANT WORK"
        details = [
            "Many components are not working",
            "Requires substantial development",
            "Architectural issues may exist"
        ]
    
    print(f"   {verdict}")
    for detail in details:
        print(f"     • {detail}")
    
    print(f"\n📝 RECOMMENDATIONS:")
    
    recommendations = []
    
    if not any("config" in r[0].lower() and r[1] for r in results):
        recommendations.append("Fix configuration system - it's fundamental")
    
    if not any("stdio" in r[0].lower() and r[1] for r in results):
        recommendations.append("Fix STDIO transport - needed for basic MCP communication")
    
    if passed_tests < total_tests:
        recommendations.append("Focus on getting core components working before adding features")
    
    if any("sandbox" in r[0].lower() for r in results):
        recommendations.append("Implement at least one sandbox provider (start with local/Docker)")
    
    if any("chaos" in r[0].lower() for r in results):
        recommendations.append("Implement chaos engineering execution components")
    
    if not recommendations:
        recommendations = [
            "Add integration tests with real MCP servers",
            "Implement remaining sandbox providers",
            "Add comprehensive documentation",
            "Build out observability features"
        ]
    
    for i, rec in enumerate(recommendations, 1):
        print(f"   {i}. {rec}")
    
    print(f"\n{'#'*80}")

def main():
    """Run all reality tests."""
    test_dir = Path(__file__).parent
    
    # Find all test files
    test_files = sorted([
        f for f in test_dir.glob("test_*.py") 
        if f.name != "test_reality.py" and f.name != Path(__file__).name
    ])
    
    if not test_files:
        print("❌ No test files found!")
        return False
    
    print(f"🚀 Running {len(test_files)} reality tests...")
    
    results = []
    
    for test_file in test_files:
        result = run_test(test_file)
        results.append(result)
        
        # Brief status update
        test_name, success, _, duration = result
        status = "✅" if success else "❌"
        print(f"\n{status} {test_name} completed in {duration:.1f}s")
    
    # Generate comprehensive report
    generate_report(results)
    
    # Return overall success
    passed = sum(1 for _, success, _, _ in results if success)
    return passed >= len(results) * 0.6  # 60% pass rate required

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)