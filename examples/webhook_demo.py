#!/usr/bin/env python3
"""
Webhook Integration Demo for MCP Reliability Lab
Shows how to send test results to Slack/Discord
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from webhook_integration import WebhookIntegration
from benchmarking.benchmark_runner import BenchmarkRunner
from benchmarking.workloads import StandardWorkloads
from config import TEST_DIR


async def run_benchmark_with_notifications():
    """Run benchmark and send results via webhook."""
    
    print("=" * 60)
    print("MCP LAB - WEBHOOK NOTIFICATION DEMO")
    print("=" * 60)
    
    # Get webhook URL from environment or use a test webhook
    webhook_url = os.getenv("WEBHOOK_URL")
    
    if not webhook_url:
        print("\nNo WEBHOOK_URL environment variable set.")
        print("To use webhooks, set one of these:")
        print("  export WEBHOOK_URL='https://hooks.slack.com/services/...'")
        print("  export WEBHOOK_URL='https://discord.com/api/webhooks/...'")
        print("\nContinuing with demo (webhook disabled)...")
        webhook_client = None
    else:
        # Detect webhook type
        if "slack" in webhook_url:
            webhook_type = "slack"
        elif "discord" in webhook_url:
            webhook_type = "discord"
        else:
            webhook_type = "generic"
        
        print(f"\nUsing {webhook_type} webhook")
        webhook_client = WebhookIntegration(webhook_url, webhook_type)
    
    # Run quick benchmark
    print("\n1. Running benchmark...")
    print("-" * 40)
    
    runner = BenchmarkRunner()
    workload = StandardWorkloads.get_quick_benchmarks()["quick_mixed"]
    workload.duration_seconds = 5  # Quick 5-second test
    
    server_config = {
        "name": "filesystem",
        "type": "filesystem",
        "path": TEST_DIR
    }
    
    # Send start notification
    if webhook_client:
        await webhook_client.send_test_start("filesystem", workload.name)
        print("Sent start notification")
    
    # Run benchmark
    results = await runner.run_benchmark(server_config, workload)
    
    # Send completion notification
    if webhook_client:
        await webhook_client.send_test_complete(
            server_name="filesystem",
            test_name=workload.name,
            duration=results['duration'],
            success_rate=1 - results['error_rate'],
            operations=results['operations_completed']
        )
        print("Sent completion notification")
        
        # Send benchmark results
        await webhook_client.send_benchmark_results(results)
        print("Sent benchmark results")
        
        # Send error notification if there were errors
        if results['errors'] > 0:
            await webhook_client.send_error(
                server_name="filesystem",
                error_message=f"Benchmark had {results['errors']} errors",
                error_details={
                    "error_rate": f"{results['error_rate']*100:.1f}%",
                    "total_operations": results['operations_completed'] + results['errors']
                }
            )
            print("Sent error notification")
    
    # Display results
    print("\n2. Benchmark Results")
    print("-" * 40)
    print(f"Operations: {results['operations_completed']}")
    print(f"Throughput: {results['operations_per_second']:.1f} ops/sec")
    print(f"Error Rate: {results['error_rate']*100:.1f}%")
    print(f"P95 Latency: {results['latencies']['p95']:.1f}ms")
    
    if webhook_client:
        print("\n3. Webhook Notifications")
        print("-" * 40)
        print("✓ Start notification sent")
        print("✓ Completion notification sent")
        print("✓ Benchmark results sent")
        if results['errors'] > 0:
            print("✓ Error notification sent")
    else:
        print("\n3. Webhook Notifications")
        print("-" * 40)
        print("✗ Skipped (no webhook URL configured)")
    
    print("\n" + "=" * 60)
    print("Demo completed successfully!")
    
    if not webhook_client:
        print("\nTo enable webhook notifications:")
        print("1. Get a webhook URL from Slack or Discord")
        print("2. Set the WEBHOOK_URL environment variable")
        print("3. Run this demo again")
    
    return 0


async def main():
    """Main entry point."""
    try:
        return await run_benchmark_with_notifications()
    except Exception as e:
        print(f"\nError: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)