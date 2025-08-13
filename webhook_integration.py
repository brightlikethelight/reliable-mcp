#!/usr/bin/env python3
"""
Webhook Integration for MCP Reliability Lab.
Sends test results and notifications to external systems.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import httpx
from pathlib import Path
import sys

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from config import get_config

logger = logging.getLogger(__name__)


class WebhookIntegration:
    """Send MCP test results to webhooks."""
    
    def __init__(self, webhook_urls: Optional[List[str]] = None):
        """Initialize webhook integration.
        
        Args:
            webhook_urls: List of webhook URLs to send notifications to
        """
        self.webhook_urls = webhook_urls or []
        self.client = httpx.AsyncClient(timeout=10.0)
        self.enabled = len(self.webhook_urls) > 0
    
    async def send_test_result(self, test_result: Dict[str, Any]) -> bool:
        """Send test result to all configured webhooks.
        
        Args:
            test_result: Test result data
            
        Returns:
            True if at least one webhook succeeded
        """
        if not self.enabled:
            return True
        
        payload = self._format_test_payload(test_result)
        success_count = 0
        
        for url in self.webhook_urls:
            try:
                response = await self.client.post(url, json=payload)
                if response.status_code in [200, 201, 202, 204]:
                    success_count += 1
                    logger.info(f"Webhook sent successfully to {url}")
                else:
                    logger.warning(f"Webhook failed to {url}: {response.status_code}")
            except Exception as e:
                logger.error(f"Error sending webhook to {url}: {e}")
        
        return success_count > 0
    
    async def send_benchmark_result(self, benchmark_result: Dict[str, Any]) -> bool:
        """Send benchmark result to webhooks.
        
        Args:
            benchmark_result: Benchmark result data
            
        Returns:
            True if at least one webhook succeeded
        """
        if not self.enabled:
            return True
        
        payload = self._format_benchmark_payload(benchmark_result)
        return await self._send_payload(payload)
    
    async def send_alert(self, alert_type: str, message: str, data: Optional[Dict] = None) -> bool:
        """Send an alert notification.
        
        Args:
            alert_type: Type of alert (error, warning, info)
            message: Alert message
            data: Additional data
            
        Returns:
            True if at least one webhook succeeded
        """
        if not self.enabled:
            return True
        
        payload = {
            "type": "mcp_lab_alert",
            "alert_type": alert_type,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data or {}
        }
        
        return await self._send_payload(payload)
    
    def _format_test_payload(self, test_result: Dict[str, Any]) -> Dict[str, Any]:
        """Format test result for webhook."""
        return {
            "type": "mcp_lab_test_result",
            "timestamp": datetime.utcnow().isoformat(),
            "test_id": test_result.get("test_id"),
            "test_name": test_result.get("name"),
            "reliability_score": test_result.get("reliability_score", 0),
            "passed": test_result.get("passed", 0),
            "failed": test_result.get("failed", 0),
            "total": test_result.get("total", 0),
            "avg_latency_ms": test_result.get("avg_latency", 0),
            "server": test_result.get("server", "unknown"),
            "status": "success" if test_result.get("reliability_score", 0) > 70 else "failure",
            "details": test_result
        }
    
    def _format_benchmark_payload(self, benchmark_result: Dict[str, Any]) -> Dict[str, Any]:
        """Format benchmark result for webhook."""
        return {
            "type": "mcp_lab_benchmark_result",
            "timestamp": datetime.utcnow().isoformat(),
            "benchmark_id": benchmark_result.get("benchmark_id"),
            "server": benchmark_result.get("server", "unknown"),
            "workload": benchmark_result.get("workload", "unknown"),
            "duration_seconds": benchmark_result.get("duration_seconds", 0),
            "operations_per_second": benchmark_result.get("operations_per_second", 0),
            "total_operations": benchmark_result.get("total_operations", 0),
            "error_rate": benchmark_result.get("error_rate", 0),
            "latencies": benchmark_result.get("latencies", {}),
            "status": "success" if benchmark_result.get("error_rate", 1) < 0.1 else "degraded",
            "details": benchmark_result
        }
    
    async def _send_payload(self, payload: Dict[str, Any]) -> bool:
        """Send payload to all webhooks."""
        success_count = 0
        
        for url in self.webhook_urls:
            try:
                response = await self.client.post(url, json=payload)
                if response.status_code in [200, 201, 202, 204]:
                    success_count += 1
                    logger.info(f"Webhook sent to {url}")
                else:
                    logger.warning(f"Webhook failed to {url}: {response.status_code}")
            except Exception as e:
                logger.error(f"Error sending webhook to {url}: {e}")
        
        return success_count > 0
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    def add_webhook(self, url: str):
        """Add a webhook URL."""
        if url not in self.webhook_urls:
            self.webhook_urls.append(url)
            self.enabled = True
    
    def remove_webhook(self, url: str):
        """Remove a webhook URL."""
        if url in self.webhook_urls:
            self.webhook_urls.remove(url)
            self.enabled = len(self.webhook_urls) > 0


class SlackWebhook(WebhookIntegration):
    """Specialized webhook for Slack notifications."""
    
    def __init__(self, webhook_url: str):
        """Initialize Slack webhook.
        
        Args:
            webhook_url: Slack incoming webhook URL
        """
        super().__init__([webhook_url])
        self.slack_url = webhook_url
    
    async def send_test_summary(self, test_result: Dict[str, Any]) -> bool:
        """Send formatted test summary to Slack."""
        
        score = test_result.get("reliability_score", 0)
        emoji = "✅" if score > 90 else "⚠️" if score > 70 else "❌"
        color = "good" if score > 90 else "warning" if score > 70 else "danger"
        
        payload = {
            "text": f"{emoji} MCP Test Result: {test_result.get('name', 'Unknown')}",
            "attachments": [{
                "color": color,
                "fields": [
                    {
                        "title": "Reliability Score",
                        "value": f"{score:.1f}%",
                        "short": True
                    },
                    {
                        "title": "Tests Passed",
                        "value": f"{test_result.get('passed', 0)}/{test_result.get('total', 0)}",
                        "short": True
                    },
                    {
                        "title": "Average Latency",
                        "value": f"{test_result.get('avg_latency', 0):.2f}ms",
                        "short": True
                    },
                    {
                        "title": "Server",
                        "value": test_result.get('server', 'unknown'),
                        "short": True
                    }
                ],
                "footer": "MCP Reliability Lab",
                "ts": int(datetime.utcnow().timestamp())
            }]
        }
        
        try:
            response = await self.client.post(self.slack_url, json=payload)
            return response.status_code in [200, 201, 202, 204]
        except Exception as e:
            logger.error(f"Error sending Slack webhook: {e}")
            return False


class DiscordWebhook(WebhookIntegration):
    """Specialized webhook for Discord notifications."""
    
    def __init__(self, webhook_url: str):
        """Initialize Discord webhook.
        
        Args:
            webhook_url: Discord webhook URL
        """
        super().__init__([webhook_url])
        self.discord_url = webhook_url
    
    async def send_test_summary(self, test_result: Dict[str, Any]) -> bool:
        """Send formatted test summary to Discord."""
        
        score = test_result.get("reliability_score", 0)
        color = 0x00ff00 if score > 90 else 0xffff00 if score > 70 else 0xff0000
        
        payload = {
            "embeds": [{
                "title": f"MCP Test Result: {test_result.get('name', 'Unknown')}",
                "color": color,
                "fields": [
                    {
                        "name": "Reliability Score",
                        "value": f"{score:.1f}%",
                        "inline": True
                    },
                    {
                        "name": "Tests Passed",
                        "value": f"{test_result.get('passed', 0)}/{test_result.get('total', 0)}",
                        "inline": True
                    },
                    {
                        "name": "Average Latency",
                        "value": f"{test_result.get('avg_latency', 0):.2f}ms",
                        "inline": True
                    },
                    {
                        "name": "Server",
                        "value": test_result.get('server', 'unknown'),
                        "inline": True
                    }
                ],
                "footer": {
                    "text": "MCP Reliability Lab"
                },
                "timestamp": datetime.utcnow().isoformat()
            }]
        }
        
        try:
            response = await self.client.post(self.discord_url, json=payload)
            return response.status_code in [200, 201, 202, 204]
        except Exception as e:
            logger.error(f"Error sending Discord webhook: {e}")
            return False


# Demo/Test code
async def demo_webhooks():
    """Demonstrate webhook functionality."""
    
    print("MCP Reliability Lab - Webhook Integration Demo")
    print("=" * 50)
    
    # Create webhook integration
    webhook = WebhookIntegration([
        "https://webhook.site/unique-id",  # Replace with your webhook URL
        "https://httpbin.org/post"  # Test endpoint
    ])
    
    # Sample test result
    test_result = {
        "test_id": "test_123",
        "name": "Demo Test Suite",
        "reliability_score": 85.5,
        "passed": 17,
        "failed": 3,
        "total": 20,
        "avg_latency": 125.3,
        "server": "filesystem"
    }
    
    print("\n1. Sending test result webhook...")
    success = await webhook.send_test_result(test_result)
    print(f"   Result: {'Success' if success else 'Failed'}")
    
    # Sample benchmark result
    benchmark_result = {
        "benchmark_id": "bench_456",
        "server": "filesystem",
        "workload": "crud_heavy",
        "duration_seconds": 30,
        "operations_per_second": 125.6,
        "total_operations": 3768,
        "error_rate": 0.02,
        "latencies": {
            "p50": 7.5,
            "p95": 15.2,
            "p99": 28.9
        }
    }
    
    print("\n2. Sending benchmark webhook...")
    success = await webhook.send_benchmark_result(benchmark_result)
    print(f"   Result: {'Success' if success else 'Failed'}")
    
    # Send alert
    print("\n3. Sending alert webhook...")
    success = await webhook.send_alert(
        "warning",
        "High error rate detected in MCP server",
        {"error_rate": 0.15, "server": "filesystem"}
    )
    print(f"   Result: {'Success' if success else 'Failed'}")
    
    await webhook.close()
    
    print("\n" + "=" * 50)
    print("Webhook demo complete!")
    print("\nTo use webhooks in your tests:")
    print("1. Create WebhookIntegration with your webhook URLs")
    print("2. Call send_test_result() after tests complete")
    print("3. Use SlackWebhook or DiscordWebhook for formatted messages")


if __name__ == "__main__":
    asyncio.run(demo_webhooks())