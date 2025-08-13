#!/usr/bin/env python3
"""
Remote Deployment Validator Demo
Demonstrates comprehensive testing of MCP server deployment readiness.
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from remote_deployment_validator import (
    RemoteDeploymentValidator,
    AuthenticationConfig,
    DeploymentValidationLevel
)


async def demo_deployment_validation():
    """Demonstrate remote deployment validation capabilities."""
    
    print("🚀 Remote Deployment Validator Demo")
    print("=" * 50)
    
    # Test different server configurations
    test_scenarios = [
        {
            "name": "Production HTTPS Server",
            "url": "https://httpbin.org",  # Public test API
            "auth": AuthenticationConfig(
                auth_type="jwt",
                scope=["read", "write"],
                jwt_secret="demo-secret-key"
            )
        },
        {
            "name": "Development HTTP Server", 
            "url": "http://httpbin.org",  # Insecure version
            "auth": AuthenticationConfig(
                auth_type="bearer"
            )
        },
        {
            "name": "OAuth2 Server",
            "url": "https://httpbin.org",
            "auth": AuthenticationConfig(
                auth_type="oauth2",
                client_id="demo-client",
                client_secret="demo-secret",
                token_endpoint="https://httpbin.org/post",  # Mock endpoint
                scope=["api:read", "api:write"]
            )
        }
    ]
    
    async with RemoteDeploymentValidator(timeout=10) as validator:
        
        for i, scenario in enumerate(test_scenarios, 1):
            print(f"\n📋 Scenario {i}: {scenario['name']}")
            print("-" * 40)
            
            try:
                report = await validator.validate_deployment(
                    server_url=scenario['url'],
                    auth_config=scenario['auth']
                )
                
                # Print summary
                print(f"✅ Security Score: {report.security_score}/100")
                print(f"🎯 Deployment Ready: {'Yes' if report.deployment_ready else 'No'}")
                print(f"📊 Checks: {report.checks_passed} passed, {report.checks_failed} failed")
                
                if report.critical_issues > 0:
                    print(f"⚠️  Critical Issues: {report.critical_issues}")
                
                # Show key findings
                print("\n🔍 Key Findings:")
                
                # Group results by category
                categories = {}
                for result in report.validations:
                    if result.category not in categories:
                        categories[result.category] = []
                    categories[result.category].append(result)
                
                for category, results in categories.items():
                    critical = len([r for r in results if r.level == DeploymentValidationLevel.CRITICAL])
                    errors = len([r for r in results if r.level == DeploymentValidationLevel.ERROR])
                    warnings = len([r for r in results if r.level == DeploymentValidationLevel.WARNING])
                    info = len([r for r in results if r.level == DeploymentValidationLevel.INFO])
                    
                    status = "🔴" if critical > 0 else "🟠" if errors > 0 else "🟡" if warnings > 0 else "🟢"
                    print(f"  {status} {category.title()}: {info} good, {warnings} warnings, {errors} errors, {critical} critical")
                
                # Save detailed report
                report_filename = f"deployment_report_{scenario['name'].lower().replace(' ', '_')}.json"
                validator.save_report(report, report_filename)
                print(f"💾 Detailed report saved: {report_filename}")
                
            except Exception as e:
                print(f"❌ Validation failed: {str(e)}")
    
    print(f"\n🎉 Demo completed! Check the JSON reports for detailed findings.")


async def demo_security_focus():
    """Demonstrate security-focused validation."""
    
    print("\n🔒 Security-Focused Validation Demo")
    print("=" * 50)
    
    # Test a server with security configurations
    auth_config = AuthenticationConfig(
        auth_type="jwt",
        jwt_secret="secure-secret-key-12345",
        jwt_algorithm="HS256",
        scope=["api:read", "api:write", "admin"]
    )
    
    async with RemoteDeploymentValidator() as validator:
        
        print("🔍 Testing security configurations...")
        
        report = await validator.validate_deployment(
            server_url="https://httpbin.org",
            auth_config=auth_config
        )
        
        print(f"\n🛡️  Security Analysis Results:")
        print(f"Overall Security Score: {report.security_score}/100")
        
        # Focus on security results
        security_results = [r for r in report.validations if r.category == "security"]
        
        if security_results:
            print(f"\n🔐 Security Checks ({len(security_results)} total):")
            
            for result in security_results:
                level_icon = {
                    DeploymentValidationLevel.CRITICAL: "🚨",
                    DeploymentValidationLevel.ERROR: "❌",
                    DeploymentValidationLevel.WARNING: "⚠️",
                    DeploymentValidationLevel.INFO: "✅"
                }.get(result.level, "❓")
                
                print(f"  {level_icon} {result.check}: {result.message}")
                
                if result.remediation:
                    print(f"    💡 Remediation: {result.remediation}")
        
        # Security summary
        print(f"\n📋 Security Summary:")
        for check, status in report.security_summary.items():
            print(f"  {'✅' if status else '❌'} {check.replace('_', ' ').title()}")
        
        # Performance impact
        if report.performance_metrics:
            print(f"\n⚡ Performance Impact:")
            for metric, value in report.performance_metrics.items():
                if "latency" in metric and isinstance(value, (int, float)):
                    print(f"  📊 {metric}: {value:.2f}ms")


def main():
    """Run the demo."""
    
    print("🔧 Remote Deployment Validator - Comprehensive Demo")
    print("This demo shows validation of MCP server deployment readiness")
    print("including security, authentication, and performance testing.\n")
    
    try:
        # Run basic deployment validation demo
        asyncio.run(demo_deployment_validation())
        
        # Run security-focused demo
        asyncio.run(demo_security_focus())
        
        print("\n✨ All demos completed successfully!")
        print("\nThe Remote Deployment Validator helps ensure MCP servers are:")
        print("• Properly authenticated and authorized")
        print("• Secured with HTTPS/TLS")
        print("• Protected against common attacks")
        print("• Ready for production deployment")
        print("• Compliant with security best practices")
        
    except KeyboardInterrupt:
        print("\n👋 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {str(e)}")
        print("Make sure you have the required dependencies installed:")
        print("pip install PyJWT cryptography aiohttp httpx")


if __name__ == "__main__":
    main()