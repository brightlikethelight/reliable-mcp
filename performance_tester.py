#!/usr/bin/env python3
"""
Performance Testing Module for MCP Servers
Benchmarks latency, throughput, and scalability.
"""

import asyncio
import time
import statistics
from typing import Dict, List, Any
import aiohttp


class PerformanceTester:
    """Performance benchmarking for MCP servers."""
    
    def __init__(self):
        self.session: aiohttp.ClientSession = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def benchmark(self, server_url: str, duration_seconds: int = 10) -> Dict:
        """Run performance benchmarks."""
        
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        results = {
            "latency_ms": 0,
            "throughput_rps": 0,
            "concurrent_connections": 0,
            "p50_latency_ms": 0,
            "p95_latency_ms": 0,
            "p99_latency_ms": 0,
            "error_rate": 0,
            "successful_requests": 0,
            "failed_requests": 0
        }
        
        # Test latency
        latencies = await self._test_latency(server_url)
        if latencies:
            results["latency_ms"] = statistics.mean(latencies)
            results["p50_latency_ms"] = statistics.median(latencies)
            if len(latencies) > 20:
                results["p95_latency_ms"] = sorted(latencies)[int(len(latencies) * 0.95)]
                results["p99_latency_ms"] = sorted(latencies)[int(len(latencies) * 0.99)]
        
        # Test throughput
        throughput_data = await self._test_throughput(server_url, duration_seconds)
        results.update(throughput_data)
        
        # Test concurrent connections
        concurrency_data = await self._test_concurrency(server_url)
        results["concurrent_connections"] = concurrency_data["max_concurrent"]
        
        return results
    
    async def _test_latency(self, server_url: str, samples: int = 100) -> List[float]:
        """Test request latency."""
        
        latencies = []
        
        for _ in range(samples):
            try:
                start = time.time()
                async with self.session.get(f"{server_url}/health") as response:
                    if response.status < 500:
                        latency = (time.time() - start) * 1000  # Convert to ms
                        latencies.append(latency)
                await asyncio.sleep(0.01)  # Small delay between requests
            except:
                pass
        
        return latencies
    
    async def _test_throughput(self, server_url: str, duration: int) -> Dict:
        """Test maximum throughput."""
        
        start_time = time.time()
        successful = 0
        failed = 0
        
        async def make_request():
            nonlocal successful, failed
            try:
                async with self.session.get(f"{server_url}/health") as response:
                    if response.status < 500:
                        successful += 1
                    else:
                        failed += 1
            except:
                failed += 1
        
        # Create continuous load
        while time.time() - start_time < duration:
            tasks = [make_request() for _ in range(10)]
            await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.sleep(0.1)
        
        elapsed = time.time() - start_time
        total_requests = successful + failed
        
        return {
            "throughput_rps": total_requests / elapsed if elapsed > 0 else 0,
            "successful_requests": successful,
            "failed_requests": failed,
            "error_rate": failed / total_requests if total_requests > 0 else 0
        }
    
    async def _test_concurrency(self, server_url: str) -> Dict:
        """Test maximum concurrent connections."""
        
        max_concurrent = 0
        
        for concurrent in [10, 50, 100, 200, 500]:
            try:
                tasks = [
                    self.session.get(f"{server_url}/health")
                    for _ in range(concurrent)
                ]
                
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Count successful responses
                successful = sum(
                    1 for r in responses
                    if not isinstance(r, Exception) and hasattr(r, 'status') and r.status < 500
                )
                
                # Close all responses
                for r in responses:
                    if not isinstance(r, Exception):
                        r.close()
                
                if successful >= concurrent * 0.8:  # 80% success rate
                    max_concurrent = concurrent
                else:
                    break
                    
            except:
                break
        
        return {"max_concurrent": max_concurrent}


async def main():
    """Example usage."""
    
    async with PerformanceTester() as tester:
        results = await tester.benchmark("https://example-mcp-server.com")
        
        print("Performance Test Results:")
        print(f"Average Latency: {results['latency_ms']:.2f}ms")
        print(f"Throughput: {results['throughput_rps']:.1f} req/s")
        print(f"Max Concurrent: {results['concurrent_connections']}")
        print(f"Error Rate: {results['error_rate']*100:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())