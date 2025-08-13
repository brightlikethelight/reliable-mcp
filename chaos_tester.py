#!/usr/bin/env python3
"""
Chaos Engineering Module for MCP Servers
Tests resilience and recovery capabilities.
"""

import asyncio
import random
import time
from typing import Dict, List, Any
import aiohttp


class ChaosTester:
    """Chaos engineering tests for MCP servers."""
    
    def __init__(self):
        self.session: aiohttp.ClientSession = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_resilience(self, server_url: str) -> Dict:
        """Run chaos engineering tests."""
        
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        results = {
            "uptime_percentage": 0,
            "error_rate": 0,
            "recovery_time_ms": 0,
            "circuit_breaker_works": False,
            "rate_limiting_works": False,
            "handles_timeouts": False,
            "handles_malformed_requests": False,
            "graceful_degradation": False
        }
        
        # Test uptime under load
        uptime_data = await self._test_uptime(server_url)
        results["uptime_percentage"] = uptime_data["uptime_percentage"]
        results["error_rate"] = uptime_data["error_rate"]
        
        # Test recovery from failures
        recovery_data = await self._test_recovery(server_url)
        results["recovery_time_ms"] = recovery_data["recovery_time_ms"]
        
        # Test circuit breaker
        results["circuit_breaker_works"] = await self._test_circuit_breaker(server_url)
        
        # Test rate limiting
        results["rate_limiting_works"] = await self._test_rate_limiting(server_url)
        
        # Test timeout handling
        results["handles_timeouts"] = await self._test_timeout_handling(server_url)
        
        # Test malformed request handling
        results["handles_malformed_requests"] = await self._test_malformed_requests(server_url)
        
        # Test graceful degradation
        results["graceful_degradation"] = await self._test_graceful_degradation(server_url)
        
        return results
    
    async def _test_uptime(self, server_url: str, duration_seconds: int = 30) -> Dict:
        """Test server uptime under various conditions."""
        
        start_time = time.time()
        successful_checks = 0
        failed_checks = 0
        
        while time.time() - start_time < duration_seconds:
            try:
                async with self.session.get(
                    f"{server_url}/health",
                    timeout=aiohttp.ClientTimeout(total=2)
                ) as response:
                    if response.status < 500:
                        successful_checks += 1
                    else:
                        failed_checks += 1
            except:
                failed_checks += 1
            
            # Random delay to simulate varying load
            await asyncio.sleep(random.uniform(0.1, 0.5))
        
        total_checks = successful_checks + failed_checks
        
        return {
            "uptime_percentage": (successful_checks / total_checks * 100) if total_checks > 0 else 0,
            "error_rate": failed_checks / total_checks if total_checks > 0 else 0
        }
    
    async def _test_recovery(self, server_url: str) -> Dict:
        """Test recovery time from failures."""
        
        # Simulate failure by overwhelming the server
        tasks = []
        for _ in range(100):
            task = self.session.get(f"{server_url}/health")
            tasks.append(task)
        
        # Send all requests at once
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Measure recovery time
        start_recovery = time.time()
        recovered = False
        max_wait = 10  # seconds
        
        while time.time() - start_recovery < max_wait:
            try:
                async with self.session.get(
                    f"{server_url}/health",
                    timeout=aiohttp.ClientTimeout(total=2)
                ) as response:
                    if response.status < 500:
                        recovered = True
                        break
            except:
                pass
            
            await asyncio.sleep(0.1)
        
        recovery_time = (time.time() - start_recovery) * 1000 if recovered else max_wait * 1000
        
        return {"recovery_time_ms": recovery_time}
    
    async def _test_circuit_breaker(self, server_url: str) -> bool:
        """Test if circuit breaker pattern is implemented."""
        
        # Send many failing requests
        failures = 0
        for _ in range(20):
            try:
                async with self.session.get(
                    f"{server_url}/nonexistent",
                    timeout=aiohttp.ClientTimeout(total=1)
                ) as response:
                    if response.status >= 500:
                        failures += 1
            except:
                failures += 1
        
        # Check if circuit opens (fast failures)
        start = time.time()
        try:
            async with self.session.get(
                f"{server_url}/health",
                timeout=aiohttp.ClientTimeout(total=1)
            ) as response:
                response_time = time.time() - start
                # Circuit breaker should fail fast
                return response_time < 0.1 and response.status == 503
        except:
            response_time = time.time() - start
            return response_time < 0.1  # Failed fast
    
    async def _test_rate_limiting(self, server_url: str) -> bool:
        """Test if rate limiting is implemented."""
        
        rate_limited = False
        
        # Send rapid requests
        tasks = []
        for _ in range(50):
            task = self.session.get(f"{server_url}/health")
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check for rate limiting responses
        for response in responses:
            if not isinstance(response, Exception):
                if hasattr(response, 'status') and response.status == 429:
                    rate_limited = True
                response.close()
        
        return rate_limited
    
    async def _test_timeout_handling(self, server_url: str) -> bool:
        """Test if server handles timeouts gracefully."""
        
        try:
            # Use very short timeout
            async with self.session.get(
                f"{server_url}/health",
                timeout=aiohttp.ClientTimeout(total=0.001)
            ) as response:
                return False  # Should have timed out
        except asyncio.TimeoutError:
            # Expected - now check if server is still responsive
            try:
                async with self.session.get(
                    f"{server_url}/health",
                    timeout=aiohttp.ClientTimeout(total=2)
                ) as response:
                    return response.status < 500
            except:
                return False
    
    async def _test_malformed_requests(self, server_url: str) -> bool:
        """Test if server handles malformed requests gracefully."""
        
        malformed_tests = [
            # Invalid headers
            {"headers": {"Content-Type": "invalid/type"}},
            # Invalid JSON
            {"json": "{invalid json}"},
            # Huge headers
            {"headers": {"X-Custom": "A" * 10000}},
        ]
        
        for test in malformed_tests:
            try:
                async with self.session.post(
                    f"{server_url}/api/endpoint",
                    **test,
                    timeout=aiohttp.ClientTimeout(total=2)
                ) as response:
                    # Should return 4xx error, not 5xx
                    if response.status >= 500:
                        return False
            except:
                pass  # Connection errors are acceptable
        
        return True
    
    async def _test_graceful_degradation(self, server_url: str) -> bool:
        """Test if server degrades gracefully under load."""
        
        # Create increasing load
        response_times = []
        
        for concurrent in [10, 50, 100]:
            tasks = []
            for _ in range(concurrent):
                task = self.session.get(f"{server_url}/health")
                tasks.append(task)
            
            start = time.time()
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            elapsed = time.time() - start
            
            successful = 0
            for response in responses:
                if not isinstance(response, Exception):
                    if hasattr(response, 'status') and response.status < 500:
                        successful += 1
                    response.close()
            
            if successful > 0:
                response_times.append(elapsed / successful)
        
        # Check if response times degrade gracefully (not exponentially)
        if len(response_times) >= 2:
            # Response time shouldn't increase more than 5x
            return response_times[-1] < response_times[0] * 5
        
        return False


async def main():
    """Example usage."""
    
    async with ChaosTester() as tester:
        results = await tester.test_resilience("https://example-mcp-server.com")
        
        print("Chaos Engineering Results:")
        print(f"Uptime: {results['uptime_percentage']:.1f}%")
        print(f"Error Rate: {results['error_rate']*100:.1f}%")
        print(f"Recovery Time: {results['recovery_time_ms']:.0f}ms")
        print(f"Circuit Breaker: {'✓' if results['circuit_breaker_works'] else '✗'}")
        print(f"Rate Limiting: {'✓' if results['rate_limiting_works'] else '✗'}")
        print(f"Graceful Degradation: {'✓' if results['graceful_degradation'] else '✗'}")


if __name__ == "__main__":
    asyncio.run(main())