#!/usr/bin/env python3
"""
Example 02: Scientific Testing
This example demonstrates property-based testing and chaos engineering.
"""

import asyncio
import random
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scientific_test_runner_improved import ImprovedScientificTestRunner
from property_tests.hypothesis_tests import PropertyTestSuite
from chaos_tests.fault_injection import ChaosTestSuite


async def run_property_tests():
    """Run property-based tests with random inputs."""
    
    print("\n🔬 Property-Based Testing")
    print("-" * 30)
    
    suite = PropertyTestSuite()
    
    # Test with random file names
    print("1. Testing with random file names...")
    for i in range(5):
        # Generate random filename
        filename = f"test_{''.join(random.choices('abcdef0123456789', k=8))}.txt"
        path = f"/tmp/mcp-test/{filename}"
        
        try:
            # Test file operations with this random name
            result = await suite.test_file_operations(path)
            print(f"   ✅ Test {i+1}: {filename} - Success")
        except Exception as e:
            print(f"   ❌ Test {i+1}: {filename} - Failed: {e}")
    
    # Test with edge cases
    print("\n2. Testing edge cases...")
    edge_cases = [
        "",                          # Empty content
        "a" * 10000,                # Large content
        "Hello\nWorld\n\t🎉",       # Special characters
        "../../../etc/passwd",       # Path traversal attempt
        "file with spaces.txt",      # Spaces in filename
    ]
    
    for i, content in enumerate(edge_cases):
        try:
            result = await suite.test_edge_case(content)
            print(f"   ✅ Edge case {i+1}: Handled correctly")
        except Exception as e:
            print(f"   ⚠️  Edge case {i+1}: {str(e)[:50]}...")


async def run_chaos_tests():
    """Run chaos engineering tests."""
    
    print("\n💥 Chaos Engineering Tests")
    print("-" * 30)
    
    chaos = ChaosTestSuite()
    
    # Test network latency
    print("1. Simulating network latency...")
    latencies = [100, 500, 1000, 2000]  # milliseconds
    
    for latency in latencies:
        result = await chaos.test_with_latency(latency)
        print(f"   {latency}ms latency: {'✅ Passed' if result else '❌ Failed'}")
    
    # Test random failures
    print("\n2. Simulating random failures...")
    failure_rates = [0.1, 0.25, 0.5]  # 10%, 25%, 50%
    
    for rate in failure_rates:
        success_count = 0
        total = 10
        
        for _ in range(total):
            if random.random() > rate:
                success_count += 1
        
        success_rate = (success_count / total) * 100
        print(f"   {int(rate*100)}% failure rate: {success_rate:.0f}% success")
    
    # Test timeout scenarios
    print("\n3. Testing timeout handling...")
    timeouts = [0.5, 1.0, 2.0, 5.0]  # seconds
    
    for timeout in timeouts:
        result = await chaos.test_timeout(timeout)
        print(f"   {timeout}s timeout: {'✅ Handled' if result else '❌ Failed'}")


async def run_scientific_suite():
    """Run the complete scientific test suite."""
    
    print("\n🔬 Complete Scientific Test Suite")
    print("=" * 50)
    
    runner = ImprovedScientificTestRunner()
    
    # Configure test server
    server_config = {
        "name": "filesystem",
        "type": "filesystem",
        "path": "/tmp/mcp-test"
    }
    
    print("Starting scientific test suite...")
    print("This will take approximately 30 seconds...\n")
    
    # Run the suite
    results = await runner.run_scientific_suite(server_config)
    
    # Display results
    print("\n📊 Scientific Test Results")
    print("-" * 30)
    
    score = results.get("scientific_score", {})
    
    print(f"Overall Score: {score.get('overall_score', 0):.1f}/100")
    print(f"Grade: {score.get('grade', 'F')}")
    print(f"Recommendation: {score.get('recommendation', 'Unknown')}")
    
    print("\nDetailed Scores:")
    for test_type, test_score in score.get('scores', {}).items():
        status = "✅" if test_score > 70 else "⚠️" if test_score > 50 else "❌"
        print(f"  {status} {test_type}: {test_score:.1f}/100")
    
    print("\nTest Statistics:")
    stats = results.get("statistics", {})
    print(f"  Total tests run: {stats.get('total_tests', 0)}")
    print(f"  Tests passed: {stats.get('passed', 0)}")
    print(f"  Tests failed: {stats.get('failed', 0)}")
    print(f"  Success rate: {stats.get('success_rate', 0):.1f}%")
    
    return results


async def main():
    """Main entry point."""
    
    print("🔬 MCP Reliability Lab - Scientific Testing Example")
    print("=" * 50)
    
    try:
        # Run different test types
        await run_property_tests()
        await run_chaos_tests()
        
        # Run complete suite
        results = await run_scientific_suite()
        
        # Summary
        print("\n" + "=" * 50)
        print("✅ Scientific testing example completed!")
        print("\nWhat we demonstrated:")
        print("- Property-based testing with random inputs")
        print("- Chaos engineering with fault injection")
        print("- Complete scientific test suite")
        print("\nNext steps:")
        print("- Customize test parameters in the code")
        print("- Add your own test cases")
        print("- Run against different MCP servers")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)