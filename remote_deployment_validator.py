#!/usr/bin/env python3
"""
Remote Deployment Validator for MCP Servers
Comprehensive testing for production-ready MCP server deployments.

This validator tests critical security and reliability aspects for MCP servers
in production environments including authentication, network security, and
deployment readiness.
"""

import asyncio
import json
import ssl
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple, Union
from urllib.parse import urlparse
import aiohttp
import jwt
import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


class DeploymentValidationLevel(Enum):
    """Deployment validation severity levels."""
    CRITICAL = "critical"     # Security vulnerability
    ERROR = "error"          # Deployment blocking issue
    WARNING = "warning"      # Production readiness concern
    INFO = "info"           # Best practice recommendation


@dataclass
class DeploymentValidationResult:
    """Result of a deployment validation check."""
    level: DeploymentValidationLevel
    category: str
    check: str
    message: str
    details: Optional[Dict] = None
    remediation: Optional[str] = None


@dataclass
class SecurityHeaders:
    """Security headers configuration."""
    cors_headers: Dict[str, str] = field(default_factory=dict)
    security_headers: Dict[str, str] = field(default_factory=dict)
    hsts_enabled: bool = False
    csp_enabled: bool = False
    frame_options: Optional[str] = None


@dataclass
class AuthenticationConfig:
    """Authentication configuration for testing."""
    auth_type: str = "bearer"  # bearer, oauth2, jwt, basic
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    token_endpoint: Optional[str] = None
    scope: List[str] = field(default_factory=list)
    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "HS256"


@dataclass
class DeploymentReport:
    """Complete deployment validation report."""
    server_url: str
    timestamp: str
    passed: bool
    security_score: int  # 0-100
    deployment_ready: bool
    checks_passed: int
    checks_failed: int
    critical_issues: int
    validations: List[DeploymentValidationResult] = field(default_factory=list)
    security_summary: Dict[str, bool] = field(default_factory=dict)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)


class RemoteDeploymentValidator:
    """Validates MCP server deployment readiness and security."""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
        self.test_tokens: Dict[str, str] = {}
        self.rate_limit_tests: List[Dict] = []
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    def _generate_test_jwt(self, auth_config: AuthenticationConfig) -> str:
        """Generate a test JWT token."""
        if not auth_config.jwt_secret:
            auth_config.jwt_secret = "test-secret-key-for-validation"
            
        payload = {
            "sub": "test-user",
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=1),
            "scope": " ".join(auth_config.scope) if auth_config.scope else "read write"
        }
        
        return jwt.encode(
            payload, 
            auth_config.jwt_secret, 
            algorithm=auth_config.jwt_algorithm
        )
    
    async def _test_oauth2_flow(self, auth_config: AuthenticationConfig) -> DeploymentValidationResult:
        """Test OAuth 2.0 authentication flow."""
        if not auth_config.token_endpoint:
            return DeploymentValidationResult(
                level=DeploymentValidationLevel.WARNING,
                category="authentication",
                check="oauth2_configuration",
                message="OAuth 2.0 token endpoint not configured",
                remediation="Configure token_endpoint in auth configuration"
            )
        
        try:
            # Test client credentials flow
            token_data = {
                "grant_type": "client_credentials",
                "client_id": auth_config.client_id,
                "client_secret": auth_config.client_secret,
                "scope": " ".join(auth_config.scope) if auth_config.scope else "read"
            }
            
            async with self.session.post(
                auth_config.token_endpoint,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            ) as response:
                if response.status == 200:
                    token_response = await response.json()
                    if "access_token" in token_response:
                        self.test_tokens["oauth2"] = token_response["access_token"]
                        return DeploymentValidationResult(
                            level=DeploymentValidationLevel.INFO,
                            category="authentication",
                            check="oauth2_flow",
                            message="OAuth 2.0 client credentials flow successful",
                            details={"token_type": token_response.get("token_type", "bearer")}
                        )
                
                return DeploymentValidationResult(
                    level=DeploymentValidationLevel.ERROR,
                    category="authentication",
                    check="oauth2_flow",
                    message=f"OAuth 2.0 authentication failed: {response.status}",
                    details={"status": response.status, "response": await response.text()}
                )
                
        except Exception as e:
            return DeploymentValidationResult(
                level=DeploymentValidationLevel.ERROR,
                category="authentication",
                check="oauth2_flow",
                message=f"OAuth 2.0 flow error: {str(e)}",
                remediation="Check token endpoint URL and credentials"
            )
    
    async def _test_jwt_authentication(self, server_url: str, auth_config: AuthenticationConfig) -> DeploymentValidationResult:
        """Test JWT token authentication."""
        try:
            # Generate test JWT
            test_token = self._generate_test_jwt(auth_config)
            self.test_tokens["jwt"] = test_token
            
            # Test with valid token
            headers = {"Authorization": f"Bearer {test_token}"}
            
            async with self.session.get(
                f"{server_url}/health",  # Assuming health endpoint
                headers=headers
            ) as response:
                if response.status in [200, 401, 403]:  # Expected responses
                    return DeploymentValidationResult(
                        level=DeploymentValidationLevel.INFO,
                        category="authentication",
                        check="jwt_authentication",
                        message="JWT authentication endpoint responding",
                        details={"status": response.status, "token_generated": True}
                    )
                
                return DeploymentValidationResult(
                    level=DeploymentValidationLevel.WARNING,
                    category="authentication",
                    check="jwt_authentication",
                    message=f"Unexpected JWT auth response: {response.status}",
                    details={"status": response.status}
                )
                
        except Exception as e:
            return DeploymentValidationResult(
                level=DeploymentValidationLevel.WARNING,
                category="authentication",
                check="jwt_authentication",
                message=f"JWT authentication test error: {str(e)}",
                remediation="Verify JWT configuration and server endpoints"
            )
    
    async def _test_token_propagation(self, server_url: str) -> List[DeploymentValidationResult]:
        """Test token propagation through the call chain."""
        results = []
        
        for token_type, token in self.test_tokens.items():
            try:
                headers = {"Authorization": f"Bearer {token}"}
                
                # Test multiple endpoints to verify token propagation
                test_endpoints = ["/health", "/api/v1/status", "/mcp/capabilities"]
                
                for endpoint in test_endpoints:
                    try:
                        async with self.session.get(
                            f"{server_url}{endpoint}",
                            headers=headers
                        ) as response:
                            if response.status != 404:  # Endpoint exists
                                auth_header = response.headers.get("WWW-Authenticate")
                                if response.status == 401 and auth_header:
                                    results.append(DeploymentValidationResult(
                                        level=DeploymentValidationLevel.INFO,
                                        category="authentication",
                                        check="token_propagation",
                                        message=f"Token propagation working for {token_type} on {endpoint}",
                                        details={"endpoint": endpoint, "auth_challenge": auth_header}
                                    ))
                                break
                    except:
                        continue
                        
            except Exception as e:
                results.append(DeploymentValidationResult(
                    level=DeploymentValidationLevel.WARNING,
                    category="authentication",
                    check="token_propagation",
                    message=f"Token propagation test failed for {token_type}: {str(e)}"
                ))
        
        if not results:
            results.append(DeploymentValidationResult(
                level=DeploymentValidationLevel.WARNING,
                category="authentication",
                check="token_propagation",
                message="Could not verify token propagation - no responsive endpoints found",
                remediation="Ensure server has accessible endpoints for authentication testing"
            ))
        
        return results
    
    async def _test_network_latency(self, server_url: str) -> DeploymentValidationResult:
        """Test network latency and connection handling."""
        latencies = []
        
        try:
            for i in range(5):  # 5 test requests
                start_time = time.time()
                
                async with self.session.get(f"{server_url}/health") as response:
                    latency = (time.time() - start_time) * 1000  # Convert to ms
                    latencies.append(latency)
                    
                await asyncio.sleep(0.1)  # Small delay between requests
            
            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)
            
            if avg_latency > 5000:  # 5 seconds
                level = DeploymentValidationLevel.CRITICAL
                message = f"Very high average latency: {avg_latency:.2f}ms"
            elif avg_latency > 1000:  # 1 second
                level = DeploymentValidationLevel.WARNING
                message = f"High average latency: {avg_latency:.2f}ms"
            else:
                level = DeploymentValidationLevel.INFO
                message = f"Acceptable latency: {avg_latency:.2f}ms"
            
            return DeploymentValidationResult(
                level=level,
                category="performance",
                check="network_latency",
                message=message,
                details={
                    "avg_latency_ms": avg_latency,
                    "max_latency_ms": max_latency,
                    "min_latency_ms": min(latencies),
                    "samples": len(latencies)
                }
            )
            
        except Exception as e:
            return DeploymentValidationResult(
                level=DeploymentValidationLevel.ERROR,
                category="performance",
                check="network_latency",
                message=f"Network latency test failed: {str(e)}",
                remediation="Check network connectivity and server responsiveness"
            )
    
    async def _test_tls_configuration(self, server_url: str) -> List[DeploymentValidationResult]:
        """Test HTTPS/TLS configuration."""
        results = []
        parsed_url = urlparse(server_url)
        
        if parsed_url.scheme != "https":
            results.append(DeploymentValidationResult(
                level=DeploymentValidationLevel.CRITICAL,
                category="security",
                check="tls_enabled",
                message="Server not using HTTPS - critical security issue",
                remediation="Enable HTTPS/TLS for production deployment"
            ))
            return results
        
        try:
            # Test TLS connection
            context = ssl.create_default_context()
            
            # Test with strict verification
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=context)
            ) as session:
                async with session.get(server_url) as response:
                    results.append(DeploymentValidationResult(
                        level=DeploymentValidationLevel.INFO,
                        category="security",
                        check="tls_verification",
                        message="TLS certificate verification successful",
                        details={"status": response.status}
                    ))
            
            # Test TLS version and ciphers
            try:
                import ssl
                sock = ssl.create_connection((parsed_url.hostname, parsed_url.port or 443))
                ssock = context.wrap_socket(sock, server_hostname=parsed_url.hostname)
                
                tls_version = ssock.version()
                cipher_suite = ssock.cipher()
                
                ssock.close()
                
                if tls_version in ["TLSv1.2", "TLSv1.3"]:
                    level = DeploymentValidationLevel.INFO
                    message = f"Good TLS version: {tls_version}"
                else:
                    level = DeploymentValidationLevel.WARNING
                    message = f"Outdated TLS version: {tls_version}"
                
                results.append(DeploymentValidationResult(
                    level=level,
                    category="security",
                    check="tls_version",
                    message=message,
                    details={"version": tls_version, "cipher": cipher_suite}
                ))
                
            except Exception as e:
                results.append(DeploymentValidationResult(
                    level=DeploymentValidationLevel.WARNING,
                    category="security",
                    check="tls_details",
                    message=f"Could not verify TLS details: {str(e)}"
                ))
                
        except Exception as e:
            results.append(DeploymentValidationResult(
                level=DeploymentValidationLevel.ERROR,
                category="security",
                check="tls_connection",
                message=f"TLS connection failed: {str(e)}",
                remediation="Check TLS certificate configuration"
            ))
        
        return results
    
    async def _test_security_headers(self, server_url: str) -> List[DeploymentValidationResult]:
        """Test CORS and security headers."""
        results = []
        
        try:
            async with self.session.get(server_url) as response:
                headers = response.headers
                
                # Check CORS headers
                cors_headers = {
                    "Access-Control-Allow-Origin": headers.get("Access-Control-Allow-Origin"),
                    "Access-Control-Allow-Methods": headers.get("Access-Control-Allow-Methods"),
                    "Access-Control-Allow-Headers": headers.get("Access-Control-Allow-Headers"),
                }
                
                # Security headers to check
                security_checks = {
                    "Strict-Transport-Security": "HSTS header",
                    "Content-Security-Policy": "CSP header",
                    "X-Frame-Options": "Frame options",
                    "X-Content-Type-Options": "Content type options",
                    "Referrer-Policy": "Referrer policy"
                }
                
                for header, description in security_checks.items():
                    if header in headers:
                        results.append(DeploymentValidationResult(
                            level=DeploymentValidationLevel.INFO,
                            category="security",
                            check="security_headers",
                            message=f"{description} present: {headers[header]}",
                            details={"header": header, "value": headers[header]}
                        ))
                    else:
                        level = DeploymentValidationLevel.CRITICAL if header == "Strict-Transport-Security" else DeploymentValidationLevel.WARNING
                        results.append(DeploymentValidationResult(
                            level=level,
                            category="security",
                            check="security_headers",
                            message=f"Missing {description}",
                            remediation=f"Add {header} security header"
                        ))
                
                # Check CORS configuration
                if cors_headers["Access-Control-Allow-Origin"] == "*":
                    results.append(DeploymentValidationResult(
                        level=DeploymentValidationLevel.WARNING,
                        category="security",
                        check="cors_configuration",
                        message="CORS allows all origins - potential security risk",
                        remediation="Restrict CORS to specific trusted origins"
                    ))
                elif cors_headers["Access-Control-Allow-Origin"]:
                    results.append(DeploymentValidationResult(
                        level=DeploymentValidationLevel.INFO,
                        category="security",
                        check="cors_configuration",
                        message="CORS properly configured with specific origins"
                    ))
                
        except Exception as e:
            results.append(DeploymentValidationResult(
                level=DeploymentValidationLevel.ERROR,
                category="security",
                check="security_headers",
                message=f"Security headers test failed: {str(e)}"
            ))
        
        return results
    
    async def _test_rate_limiting(self, server_url: str) -> DeploymentValidationResult:
        """Test rate limiting and DDoS protection."""
        try:
            # Send rapid requests to test rate limiting
            start_time = time.time()
            responses = []
            
            tasks = []
            for i in range(20):  # 20 rapid requests
                task = self.session.get(f"{server_url}/health")
                tasks.append(task)
            
            # Execute requests concurrently
            for i in range(0, len(tasks), 5):  # Batch of 5
                batch = tasks[i:i+5]
                batch_responses = await asyncio.gather(*batch, return_exceptions=True)
                
                for resp in batch_responses:
                    if isinstance(resp, Exception):
                        responses.append({"status": "error", "error": str(resp)})
                    else:
                        responses.append({
                            "status": resp.status,
                            "headers": dict(resp.headers)
                        })
                        resp.close()
                
                await asyncio.sleep(0.1)  # Small delay between batches
            
            # Analyze responses for rate limiting
            status_codes = [r.get("status") for r in responses if isinstance(r.get("status"), int)]
            rate_limited = len([s for s in status_codes if s == 429])  # Too Many Requests
            
            total_time = time.time() - start_time
            requests_per_second = len(responses) / total_time
            
            if rate_limited > 0:
                return DeploymentValidationResult(
                    level=DeploymentValidationLevel.INFO,
                    category="security",
                    check="rate_limiting",
                    message=f"Rate limiting active - {rate_limited} requests limited",
                    details={
                        "rate_limited_requests": rate_limited,
                        "total_requests": len(responses),
                        "requests_per_second": requests_per_second
                    }
                )
            else:
                return DeploymentValidationResult(
                    level=DeploymentValidationLevel.WARNING,
                    category="security",
                    check="rate_limiting",
                    message="No rate limiting detected - potential DDoS vulnerability",
                    remediation="Implement rate limiting to prevent abuse",
                    details={
                        "requests_per_second": requests_per_second,
                        "total_requests": len(responses)
                    }
                )
                
        except Exception as e:
            return DeploymentValidationResult(
                level=DeploymentValidationLevel.ERROR,
                category="security",
                check="rate_limiting",
                message=f"Rate limiting test failed: {str(e)}"
            )
    
    async def _test_sso_integration(self, server_url: str, auth_config: AuthenticationConfig) -> DeploymentValidationResult:
        """Test SSO integration readiness."""
        try:
            # Check for common SSO endpoints
            sso_endpoints = [
                "/.well-known/openid_configuration",
                "/auth/sso",
                "/saml/metadata",
                "/oauth/authorize"
            ]
            
            found_endpoints = []
            
            for endpoint in sso_endpoints:
                try:
                    async with self.session.get(f"{server_url}{endpoint}") as response:
                        if response.status != 404:
                            found_endpoints.append({
                                "endpoint": endpoint,
                                "status": response.status,
                                "content_type": response.headers.get("content-type", "")
                            })
                except:
                    continue
            
            if found_endpoints:
                return DeploymentValidationResult(
                    level=DeploymentValidationLevel.INFO,
                    category="authentication",
                    check="sso_integration",
                    message=f"SSO endpoints detected: {len(found_endpoints)}",
                    details={"endpoints": found_endpoints}
                )
            else:
                return DeploymentValidationResult(
                    level=DeploymentValidationLevel.WARNING,
                    category="authentication",
                    check="sso_integration",
                    message="No SSO endpoints detected",
                    remediation="Configure SSO integration for enterprise deployment",
                    details={"tested_endpoints": sso_endpoints}
                )
                
        except Exception as e:
            return DeploymentValidationResult(
                level=DeploymentValidationLevel.WARNING,
                category="authentication",
                check="sso_integration",
                message=f"SSO integration test failed: {str(e)}"
            )
    
    def _calculate_security_score(self, results: List[DeploymentValidationResult]) -> int:
        """Calculate overall security score (0-100)."""
        total_weight = 0
        score = 0
        
        weights = {
            DeploymentValidationLevel.CRITICAL: -30,
            DeploymentValidationLevel.ERROR: -15,
            DeploymentValidationLevel.WARNING: -5,
            DeploymentValidationLevel.INFO: +10
        }
        
        for result in results:
            if result.category == "security":
                weight = weights.get(result.level, 0)
                total_weight += abs(weight)
                score += weight
        
        # Normalize to 0-100 scale
        if total_weight > 0:
            normalized_score = max(0, min(100, 50 + (score / total_weight) * 50))
        else:
            normalized_score = 50  # Default if no security tests
        
        return int(normalized_score)
    
    async def validate_deployment(
        self,
        server_url: str,
        auth_config: Optional[AuthenticationConfig] = None
    ) -> DeploymentReport:
        """Validate MCP server deployment readiness."""
        if not self.session:
            raise RuntimeError("Validator must be used as async context manager")
        
        results = []
        start_time = datetime.utcnow()
        
        # Default auth config
        if auth_config is None:
            auth_config = AuthenticationConfig()
        
        try:
            # Test authentication
            if auth_config.auth_type == "oauth2":
                oauth_result = await self._test_oauth2_flow(auth_config)
                results.append(oauth_result)
            
            if auth_config.auth_type == "jwt":
                jwt_result = await self._test_jwt_authentication(server_url, auth_config)
                results.append(jwt_result)
            
            # Test token propagation
            if self.test_tokens:
                propagation_results = await self._test_token_propagation(server_url)
                results.extend(propagation_results)
            
            # Test network performance
            latency_result = await self._test_network_latency(server_url)
            results.append(latency_result)
            
            # Test TLS configuration
            tls_results = await self._test_tls_configuration(server_url)
            results.extend(tls_results)
            
            # Test security headers
            security_results = await self._test_security_headers(server_url)
            results.extend(security_results)
            
            # Test rate limiting
            rate_limit_result = await self._test_rate_limiting(server_url)
            results.append(rate_limit_result)
            
            # Test SSO integration
            sso_result = await self._test_sso_integration(server_url, auth_config)
            results.append(sso_result)
            
        except Exception as e:
            results.append(DeploymentValidationResult(
                level=DeploymentValidationLevel.CRITICAL,
                category="connectivity",
                check="server_connection",
                message=f"Failed to connect to server: {str(e)}",
                remediation="Check server URL and network connectivity"
            ))
        
        # Calculate metrics
        critical_issues = len([r for r in results if r.level == DeploymentValidationLevel.CRITICAL])
        error_issues = len([r for r in results if r.level == DeploymentValidationLevel.ERROR])
        checks_failed = critical_issues + error_issues
        checks_passed = len(results) - checks_failed
        
        security_score = self._calculate_security_score(results)
        passed = critical_issues == 0 and error_issues == 0
        deployment_ready = passed and security_score >= 70
        
        # Create security summary
        security_summary = {
            "tls_enabled": any(r.check == "tls_verification" and r.level == DeploymentValidationLevel.INFO for r in results),
            "security_headers": any(r.category == "security" and "header" in r.check for r in results),
            "rate_limiting": any(r.check == "rate_limiting" and "active" in r.message for r in results),
            "cors_configured": any(r.check == "cors_configuration" for r in results),
            "auth_configured": len(self.test_tokens) > 0
        }
        
        # Performance metrics
        latency_result = next((r for r in results if r.check == "network_latency"), None)
        performance_metrics = {}
        if latency_result and latency_result.details:
            performance_metrics = latency_result.details
        
        return DeploymentReport(
            server_url=server_url,
            timestamp=start_time.isoformat(),
            passed=passed,
            security_score=security_score,
            deployment_ready=deployment_ready,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            critical_issues=critical_issues,
            validations=results,
            security_summary=security_summary,
            performance_metrics=performance_metrics
        )
    
    def save_report(self, report: DeploymentReport, filepath: str):
        """Save deployment report to JSON file."""
        report_dict = {
            "server_url": report.server_url,
            "timestamp": report.timestamp,
            "passed": report.passed,
            "security_score": report.security_score,
            "deployment_ready": report.deployment_ready,
            "checks_passed": report.checks_passed,
            "checks_failed": report.checks_failed,
            "critical_issues": report.critical_issues,
            "security_summary": report.security_summary,
            "performance_metrics": report.performance_metrics,
            "validations": [
                {
                    "level": result.level.value,
                    "category": result.category,
                    "check": result.check,
                    "message": result.message,
                    "details": result.details,
                    "remediation": result.remediation
                }
                for result in report.validations
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(report_dict, f, indent=2)
    
    def print_report(self, report: DeploymentReport):
        """Print formatted deployment report."""
        print(f"\n{'='*60}")
        print(f"REMOTE DEPLOYMENT VALIDATION REPORT")
        print(f"{'='*60}")
        print(f"Server: {report.server_url}")
        print(f"Timestamp: {report.timestamp}")
        print(f"Security Score: {report.security_score}/100")
        print(f"Deployment Ready: {'✓' if report.deployment_ready else '✗'}")
        print(f"Checks Passed: {report.checks_passed}")
        print(f"Checks Failed: {report.checks_failed}")
        print(f"Critical Issues: {report.critical_issues}")
        
        if report.security_summary:
            print(f"\nSecurity Summary:")
            for check, status in report.security_summary.items():
                print(f"  {check}: {'✓' if status else '✗'}")
        
        if report.performance_metrics:
            print(f"\nPerformance Metrics:")
            for metric, value in report.performance_metrics.items():
                if isinstance(value, float):
                    print(f"  {metric}: {value:.2f}")
                else:
                    print(f"  {metric}: {value}")
        
        print(f"\nDetailed Results:")
        print(f"{'-'*60}")
        
        for result in report.validations:
            level_symbol = {
                DeploymentValidationLevel.CRITICAL: "🔴",
                DeploymentValidationLevel.ERROR: "🟠", 
                DeploymentValidationLevel.WARNING: "🟡",
                DeploymentValidationLevel.INFO: "🟢"
            }.get(result.level, "⚪")
            
            print(f"{level_symbol} [{result.category.upper()}] {result.check}")
            print(f"   {result.message}")
            
            if result.remediation:
                print(f"   Remediation: {result.remediation}")
            
            if result.details:
                print(f"   Details: {result.details}")
            print()


async def main():
    """Example usage of the Remote Deployment Validator."""
    
    # Example server URL
    server_url = "https://api.example.com"
    
    # Example authentication configuration
    auth_config = AuthenticationConfig(
        auth_type="jwt",
        scope=["read", "write"],
        jwt_secret="your-secret-key"
    )
    
    async with RemoteDeploymentValidator() as validator:
        print("Running remote deployment validation...")
        
        report = await validator.validate_deployment(
            server_url=server_url,
            auth_config=auth_config
        )
        
        # Print report
        validator.print_report(report)
        
        # Save report
        validator.save_report(report, "deployment_validation_report.json")
        
        print(f"\nDeployment validation completed!")
        print(f"Security score: {report.security_score}/100")
        print(f"Deployment ready: {report.deployment_ready}")


if __name__ == "__main__":
    asyncio.run(main())