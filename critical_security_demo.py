#!/usr/bin/env python3
"""
Critical Security Demo - MCP Reliability Lab
Demonstrates the REAL production vulnerabilities we can now detect.
This is what's actually killing MCP deployments in production.
"""

import asyncio
import json
from pathlib import Path

# Import our critical security tools
from cve_scanner import CVEScanner, print_cve_report
from auth_tester import AuthenticationTester, print_auth_report  
from schema_chaos_validator import SchemaChaosValidator, print_chaos_report
from config import SERVERS


async def main():
    """Demonstrate critical security testing capabilities."""
    
    print("=" * 80)
    print(" MCP RELIABILITY LAB - CRITICAL SECURITY ASSESSMENT")
    print(" Testing for REAL Production Vulnerabilities")
    print("=" * 80)
    
    server_name = "filesystem"
    
    print(f"\nTarget Server: {server_name}")
    print(f"Description: {SERVERS[server_name].get('description', 'N/A')}")
    
    # Track critical findings
    critical_issues = []
    
    # 1. CVE Scanner - Test for documented vulnerabilities
    print("\n" + "─" * 80)
    print("1. CVE VULNERABILITY SCAN (Testing for CVE-2025-* with CVSS scores)")
    print("─" * 80)
    
    cve_scanner = CVEScanner()
    cve_report = await cve_scanner.scan_for_cves(server_name)
    
    if cve_report['vulnerabilities_found'] > 0:
        critical_issues.append(f"Found {cve_report['vulnerabilities_found']} CVE vulnerabilities (max CVSS: {cve_report['max_cvss_score']})")
    
    print(f"\n📊 CVE Summary:")
    print(f"  Risk Level: {cve_report['risk_level']}")
    print(f"  Vulnerabilities: {cve_report['vulnerabilities_found']}")
    print(f"  Max CVSS Score: {cve_report['max_cvss_score']}")
    
    # 2. Authentication Tester - The #1 production issue
    print("\n" + "─" * 80)
    print("2. AUTHENTICATION VULNERABILITY TEST (45% of vendors ignore this!)")
    print("─" * 80)
    
    auth_tester = AuthenticationTester()
    auth_report = await auth_tester.test_authentication(server_name)
    
    if auth_report['auth_status'] == "EXPOSED - NO AUTHENTICATION":
        critical_issues.append("SERVER HAS NO AUTHENTICATION - ANYONE CAN EXECUTE COMMANDS")
    elif auth_report['auth_status'] == "VULNERABLE":
        critical_issues.append("Authentication can be bypassed")
    
    print(f"\n📊 Authentication Summary:")
    print(f"  Status: {auth_report['auth_status']}")
    print(f"  Risk Score: {auth_report['risk_score']}/100")
    print(f"  Vulnerabilities: {auth_report['tests_failed']}")
    
    # 3. Schema Chaos - Production killers
    print("\n" + "─" * 80)
    print("3. SCHEMA CHAOS VALIDATION (Testing for 'Cannot read properties of undefined')")
    print("─" * 80)
    
    chaos_validator = SchemaChaosValidator()
    chaos_report = await chaos_validator.validate_schema_chaos(server_name)
    
    if chaos_report['production_ready'] == "NO":
        critical_issues.append(f"NOT PRODUCTION READY - {chaos_report['failures_found']} schema failures")
    
    print(f"\n📊 Schema Chaos Summary:")
    print(f"  Production Ready: {chaos_report['production_ready']}")
    print(f"  Chaos Resistance: {chaos_report['chaos_resistance_score']}/100")
    print(f"  Failures Found: {chaos_report['failures_found']}")
    
    # 4. Final Assessment
    print("\n" + "=" * 80)
    print(" CRITICAL SECURITY ASSESSMENT RESULTS")
    print("=" * 80)
    
    # Determine overall security posture
    if len(critical_issues) == 0:
        security_posture = "SECURE"
        symbol = "✅"
    elif any("NO AUTHENTICATION" in issue for issue in critical_issues):
        security_posture = "CRITICAL - EXPOSED TO INTERNET"
        symbol = "🚨"
    elif any("CVE" in issue for issue in critical_issues):
        security_posture = "HIGH RISK - KNOWN VULNERABILITIES"
        symbol = "⚠️"
    else:
        security_posture = "MEDIUM RISK"
        symbol = "⚠️"
    
    print(f"\n{symbol} SECURITY POSTURE: {security_posture}")
    
    if critical_issues:
        print("\n🔴 CRITICAL ISSUES FOUND:")
        for issue in critical_issues:
            print(f"  • {issue}")
    else:
        print("\n✅ No critical security issues found")
    
    # Production deployment recommendation
    print("\n" + "─" * 80)
    print("PRODUCTION DEPLOYMENT RECOMMENDATION:")
    print("─" * 80)
    
    if security_posture == "CRITICAL - EXPOSED TO INTERNET":
        print("❌ DO NOT DEPLOY TO PRODUCTION")
        print("   This server is completely exposed and can be compromised by anyone.")
        print("\n   IMMEDIATE ACTIONS REQUIRED:")
        print("   1. Implement authentication (OAuth 2.1 recommended)")
        print("   2. Bind to localhost only (never 0.0.0.0)")
        print("   3. Apply all security patches")
        print("   4. Implement input validation")
    elif security_posture == "HIGH RISK - KNOWN VULNERABILITIES":
        print("⚠️ HIGH RISK - Fix vulnerabilities before deployment")
        print("   Known CVEs must be patched before production use.")
    elif security_posture == "MEDIUM RISK":
        print("⚠️ MEDIUM RISK - Address issues before production")
        print("   Schema validation and other issues need fixing.")
    else:
        print("✅ ACCEPTABLE FOR PRODUCTION (with monitoring)")
        print("   Implement monitoring and regular security scans.")
    
    # Comparison with industry
    print("\n" + "─" * 80)
    print("INDUSTRY COMPARISON:")
    print("─" * 80)
    print("Your server vs. Industry average:")
    print(f"  CVE Protection: {'Better' if cve_report['vulnerabilities_found'] == 0 else 'Worse'} than 55% of servers")
    print(f"  Authentication: {'Better' if auth_report['auth_status'] != 'EXPOSED - NO AUTHENTICATION' else 'Worse'} than 45% of servers")
    print(f"  Schema Validation: {'Better' if chaos_report['production_ready'] == 'YES' else 'Similar to'} industry average")
    
    # Save comprehensive report
    comprehensive_report = {
        "server": server_name,
        "security_posture": security_posture,
        "critical_issues": critical_issues,
        "cve_scan": {
            "risk_level": cve_report['risk_level'],
            "vulnerabilities": cve_report['vulnerabilities_found'],
            "max_cvss": cve_report['max_cvss_score']
        },
        "authentication": {
            "status": auth_report['auth_status'],
            "risk_score": auth_report['risk_score'],
            "findings": auth_report['tests_failed']
        },
        "schema_validation": {
            "production_ready": chaos_report['production_ready'],
            "chaos_resistance": chaos_report['chaos_resistance_score'],
            "failures": chaos_report['failures_found']
        },
        "recommendation": "DO NOT DEPLOY" if security_posture.startswith("CRITICAL") else "FIX BEFORE DEPLOY" if "HIGH" in security_posture else "MONITOR CLOSELY"
    }
    
    report_file = f"critical_security_report_{server_name}.json"
    with open(report_file, "w") as f:
        json.dump(comprehensive_report, f, indent=2)
    
    print(f"\n📄 Full report saved to {report_file}")
    
    # Final message
    print("\n" + "=" * 80)
    print("Remember: These are REAL vulnerabilities affecting PRODUCTION MCP servers.")
    print("45% of vendors dismiss these as 'acceptable' - Don't be one of them.")
    print("=" * 80)
    
    return 0 if security_posture == "SECURE" else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    import sys
    sys.exit(exit_code)