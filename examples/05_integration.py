#!/usr/bin/env python3
"""
Example 05: Integration with Your Application
Shows how to integrate MCP Reliability Lab into your own code.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_client import MCPClient
from services.test_runner_service import TestRunnerService
from services.metrics_service import MetricsService


class MCPReliabilityClient:
    """
    Simple client wrapper for integrating MCP Reliability Lab
    into your application.
    """
    
    def __init__(self, server_type: str = "filesystem"):
        self.server_type = server_type
        self.test_runner = TestRunnerService()
        self.metrics_service = MetricsService()
        self.client = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
    
    async def connect(self):
        """Connect to MCP server."""
        self.client = MCPClient(
            server_type=self.server_type,
            server_params={"working_dir": "/tmp/mcp-test"}
        )
        await self.client.start()
        print(f"✅ Connected to {self.server_type} server")
    
    async def disconnect(self):
        """Disconnect from MCP server."""
        if self.client:
            await self.client.stop()
            print(f"✅ Disconnected from {self.server_type} server")
    
    async def health_check(self) -> bool:
        """Check if server is healthy."""
        try:
            tools = await self.client.list_tools()
            return len(tools) > 0
        except:
            return False
    
    async def run_operation(self, operation: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run a single operation and track metrics."""
        
        # Record start time
        import time
        start_time = time.time()
        
        try:
            # Execute operation
            result = await self.client.call_tool(operation, params)
            
            # Record metrics
            latency = (time.time() - start_time) * 1000  # ms
            await self.metrics_service.record_metric(
                test_id=f"integration_{operation}",
                metric_type="latency",
                value=latency,
                metadata={"operation": operation, "success": True}
            )
            
            return {
                "success": True,
                "result": result,
                "latency_ms": latency
            }
            
        except Exception as e:
            # Record failure
            await self.metrics_service.record_metric(
                test_id=f"integration_{operation}",
                metric_type="error",
                value=1,
                metadata={"operation": operation, "error": str(e)}
            )
            
            return {
                "success": False,
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000
            }
    
    async def run_test_suite(self, test_name: str = "integration_test") -> Dict[str, Any]:
        """Run a predefined test suite."""
        
        test_config = {
            "name": test_name,
            "tests": [
                {
                    "name": "write_test",
                    "tool": "write_file",
                    "args": {
                        "path": "/tmp/mcp-test/integration.txt",
                        "content": "Integration test content"
                    }
                },
                {
                    "name": "read_test",
                    "tool": "read_file",
                    "args": {"path": "/tmp/mcp-test/integration.txt"}
                },
                {
                    "name": "list_test",
                    "tool": "list_directory",
                    "args": {"path": "/tmp/mcp-test"}
                }
            ]
        }
        
        return await self.test_runner.run_test(test_config)
    
    async def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of recent metrics."""
        
        metrics = await self.metrics_service.get_recent_metrics(limit=100)
        
        if not metrics:
            return {"message": "No metrics available"}
        
        # Calculate summary statistics
        latencies = [m['value'] for m in metrics if m['metric_type'] == 'latency']
        errors = [m for m in metrics if m['metric_type'] == 'error']
        
        summary = {
            "total_operations": len(metrics),
            "total_errors": len(errors),
            "error_rate": len(errors) / len(metrics) if metrics else 0,
        }
        
        if latencies:
            summary.update({
                "avg_latency_ms": sum(latencies) / len(latencies),
                "min_latency_ms": min(latencies),
                "max_latency_ms": max(latencies),
            })
        
        return summary


async def example_basic_integration():
    """Basic integration example."""
    
    print("\n📦 Basic Integration Example")
    print("-" * 40)
    
    # Use as context manager
    async with MCPReliabilityClient("filesystem") as client:
        
        # Health check
        healthy = await client.health_check()
        print(f"Server healthy: {'✅' if healthy else '❌'}")
        
        # Run some operations
        print("\nRunning operations:")
        
        # Write operation
        write_result = await client.run_operation(
            "write_file",
            {"path": "/tmp/mcp-test/example.txt", "content": "Hello Integration!"}
        )
        print(f"  Write: {'✅' if write_result['success'] else '❌'} ({write_result['latency_ms']:.1f}ms)")
        
        # Read operation
        read_result = await client.run_operation(
            "read_file",
            {"path": "/tmp/mcp-test/example.txt"}
        )
        print(f"  Read: {'✅' if read_result['success'] else '❌'} ({read_result['latency_ms']:.1f}ms)")
        
        # Get metrics summary
        summary = await client.get_metrics_summary()
        print(f"\nMetrics Summary:")
        print(f"  Total operations: {summary.get('total_operations', 0)}")
        print(f"  Error rate: {summary.get('error_rate', 0):.1%}")
        if 'avg_latency_ms' in summary:
            print(f"  Avg latency: {summary['avg_latency_ms']:.1f}ms")


async def example_automated_testing():
    """Automated testing integration example."""
    
    print("\n🤖 Automated Testing Integration")
    print("-" * 40)
    
    client = MCPReliabilityClient("filesystem")
    
    try:
        await client.connect()
        
        # Run test suite
        print("Running automated test suite...")
        results = await client.run_test_suite("automated_integration")
        
        # Check results
        reliability_score = results.get('reliability_score', 0)
        passed = results.get('passed', 0)
        total = results.get('total', 0)
        
        print(f"\nTest Results:")
        print(f"  Reliability Score: {reliability_score:.1f}%")
        print(f"  Tests Passed: {passed}/{total}")
        
        # Determine if build should pass
        if reliability_score >= 90:
            print("  ✅ Build PASSED - Reliability threshold met")
            exit_code = 0
        else:
            print("  ❌ Build FAILED - Reliability below threshold")
            exit_code = 1
        
        return exit_code
        
    finally:
        await client.disconnect()


async def example_monitoring_integration():
    """Monitoring and alerting integration example."""
    
    print("\n📊 Monitoring Integration Example")
    print("-" * 40)
    
    async def monitor_mcp_server(duration_seconds: int = 10):
        """Monitor MCP server performance."""
        
        client = MCPReliabilityClient("filesystem")
        await client.connect()
        
        print(f"Monitoring for {duration_seconds} seconds...")
        
        try:
            import time
            start_time = time.time()
            operation_count = 0
            errors = []
            
            while time.time() - start_time < duration_seconds:
                # Perform test operation
                result = await client.run_operation(
                    "list_directory",
                    {"path": "/tmp/mcp-test"}
                )
                
                operation_count += 1
                
                if not result['success']:
                    errors.append(result['error'])
                    print(f"  ⚠️ Error detected: {result['error']}")
                
                # Check performance
                if result['latency_ms'] > 1000:  # Alert if > 1 second
                    print(f"  ⚠️ High latency detected: {result['latency_ms']:.0f}ms")
                
                await asyncio.sleep(1)  # Check every second
            
            # Final report
            print(f"\nMonitoring Complete:")
            print(f"  Operations performed: {operation_count}")
            print(f"  Errors encountered: {len(errors)}")
            print(f"  Error rate: {len(errors)/operation_count*100:.1f}%")
            
            # Get overall metrics
            summary = await client.get_metrics_summary()
            print(f"  Average latency: {summary.get('avg_latency_ms', 0):.1f}ms")
            
            # Alert if needed
            if len(errors) > operation_count * 0.1:  # >10% error rate
                print("\n🚨 ALERT: High error rate detected!")
                print("  Action: Check server logs and configuration")
            
        finally:
            await client.disconnect()
    
    await monitor_mcp_server(5)  # Monitor for 5 seconds


async def example_custom_integration():
    """Custom integration for specific use case."""
    
    print("\n🔧 Custom Integration Example")
    print("-" * 40)
    
    class DocumentProcessor:
        """Example: Document processing system using MCP."""
        
        def __init__(self):
            self.mcp_client = MCPReliabilityClient("filesystem")
            self.processed_count = 0
            self.failed_count = 0
        
        async def process_document(self, doc_path: str, content: str) -> bool:
            """Process a single document."""
            
            # Write document
            result = await self.mcp_client.run_operation(
                "write_file",
                {"path": doc_path, "content": content}
            )
            
            if result['success']:
                self.processed_count += 1
                return True
            else:
                self.failed_count += 1
                return False
        
        async def process_batch(self, documents: list) -> Dict[str, Any]:
            """Process a batch of documents."""
            
            await self.mcp_client.connect()
            
            try:
                print(f"Processing {len(documents)} documents...")
                
                for i, (path, content) in enumerate(documents):
                    success = await self.process_document(path, content)
                    status = "✅" if success else "❌"
                    print(f"  Document {i+1}: {status}")
                
                # Get performance metrics
                metrics = await self.mcp_client.get_metrics_summary()
                
                return {
                    "processed": self.processed_count,
                    "failed": self.failed_count,
                    "success_rate": self.processed_count / len(documents),
                    "avg_latency_ms": metrics.get('avg_latency_ms', 0)
                }
                
            finally:
                await self.mcp_client.disconnect()
    
    # Use the custom processor
    processor = DocumentProcessor()
    
    # Sample documents
    documents = [
        (f"/tmp/mcp-test/doc{i}.txt", f"Document {i} content")
        for i in range(5)
    ]
    
    results = await processor.process_batch(documents)
    
    print(f"\nProcessing Complete:")
    print(f"  Success rate: {results['success_rate']*100:.0f}%")
    print(f"  Avg latency: {results['avg_latency_ms']:.1f}ms")


async def main():
    """Main entry point."""
    
    print("🔬 MCP Reliability Lab - Integration Examples")
    print("=" * 50)
    
    try:
        # Run different integration examples
        await example_basic_integration()
        await example_automated_testing()
        await example_monitoring_integration()
        await example_custom_integration()
        
        # Summary
        print("\n" + "=" * 50)
        print("✅ Integration examples completed!")
        print("\nWhat we demonstrated:")
        print("- Basic client integration")
        print("- Automated testing in CI/CD")
        print("- Monitoring and alerting")
        print("- Custom use case integration")
        print("\nNext steps:")
        print("- Copy the MCPReliabilityClient class to your project")
        print("- Customize for your specific needs")
        print("- Add to your test suite or monitoring")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)