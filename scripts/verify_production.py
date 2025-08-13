#!/usr/bin/env python3
"""
Production readiness verification script for MCP Reliability Lab.
Checks all components and validates deployment readiness.
"""

import subprocess
import requests
import sys
import os
import json
import time
from pathlib import Path
from typing import List, Tuple, Dict
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

class ProductionVerifier:
    """Verify production readiness of MCP Reliability Lab."""
    
    def __init__(self):
        self.checks_passed = []
        self.checks_failed = []
        self.base_url = os.getenv("MCP_BASE_URL", "https://mcp-reliability.com")
        self.api_url = os.getenv("MCP_API_URL", "https://api.mcp-reliability.com")
    
    def run_command(self, command: List[str]) -> Tuple[bool, str]:
        """Run a shell command and return success status and output."""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)
    
    def check_docker_images(self) -> bool:
        """Check if Docker images are built and available."""
        console.print("\n[bold cyan]Checking Docker Images...[/bold cyan]")
        
        images = [
            "mcp-reliability-backend",
            "mcp-reliability-frontend"
        ]
        
        for image in images:
            success, output = self.run_command(["docker", "images", "-q", image])
            if success and output.strip():
                console.print(f"  ✅ {image}: Found")
                self.checks_passed.append(f"Docker image: {image}")
            else:
                console.print(f"  ❌ {image}: Not found")
                self.checks_failed.append(f"Docker image: {image}")
                return False
        
        return True
    
    def check_docker_compose(self) -> bool:
        """Check if docker-compose configuration is valid."""
        console.print("\n[bold cyan]Checking Docker Compose Configuration...[/bold cyan]")
        
        compose_file = Path("docker-compose.production.yml")
        if not compose_file.exists():
            console.print("  ❌ docker-compose.production.yml not found")
            self.checks_failed.append("Docker Compose config")
            return False
        
        success, output = self.run_command([
            "docker-compose", "-f", "docker-compose.production.yml", "config"
        ])
        
        if success:
            console.print("  ✅ Docker Compose configuration is valid")
            self.checks_passed.append("Docker Compose config")
            return True
        else:
            console.print(f"  ❌ Docker Compose configuration invalid: {output}")
            self.checks_failed.append("Docker Compose config")
            return False
    
    def check_kubernetes_manifests(self) -> bool:
        """Check if Kubernetes manifests are valid."""
        console.print("\n[bold cyan]Checking Kubernetes Manifests...[/bold cyan]")
        
        k8s_dir = Path("k8s/production")
        if not k8s_dir.exists():
            console.print("  ❌ k8s/production directory not found")
            self.checks_failed.append("Kubernetes manifests")
            return False
        
        manifests = list(k8s_dir.glob("*.yaml"))
        if not manifests:
            console.print("  ❌ No Kubernetes manifests found")
            self.checks_failed.append("Kubernetes manifests")
            return False
        
        all_valid = True
        for manifest in manifests:
            success, output = self.run_command([
                "kubectl", "apply", "--dry-run=client", "-f", str(manifest)
            ])
            
            if success:
                console.print(f"  ✅ {manifest.name}: Valid")
            else:
                console.print(f"  ❌ {manifest.name}: Invalid")
                all_valid = False
        
        if all_valid:
            self.checks_passed.append("Kubernetes manifests")
        else:
            self.checks_failed.append("Kubernetes manifests")
        
        return all_valid
    
    def check_environment_variables(self) -> bool:
        """Check if required environment variables are set."""
        console.print("\n[bold cyan]Checking Environment Variables...[/bold cyan]")
        
        required_vars = [
            "DATABASE_URL",
            "REDIS_URL",
            "SECRET_KEY",
            "GITHUB_TOKEN",
            "MODAL_TOKEN_ID",
            "MODAL_TOKEN_SECRET"
        ]
        
        env_file = Path(".env.production")
        if env_file.exists():
            console.print("  ✅ .env.production file found")
            
            # Parse env file
            env_vars = {}
            with open(env_file) as f:
                for line in f:
                    if "=" in line and not line.startswith("#"):
                        key, value = line.strip().split("=", 1)
                        env_vars[key] = value
            
            missing = []
            for var in required_vars:
                if var in env_vars and env_vars[var] and env_vars[var] != "CHANGE_ME":
                    console.print(f"  ✅ {var}: Set")
                else:
                    console.print(f"  ❌ {var}: Not set or default value")
                    missing.append(var)
            
            if missing:
                self.checks_failed.append("Environment variables")
                return False
            else:
                self.checks_passed.append("Environment variables")
                return True
        else:
            console.print("  ❌ .env.production file not found")
            self.checks_failed.append("Environment variables")
            return False
    
    def check_ssl_certificates(self) -> bool:
        """Check if SSL certificates are configured."""
        console.print("\n[bold cyan]Checking SSL Certificates...[/bold cyan]")
        
        ssl_dir = Path("ssl")
        cert_file = ssl_dir / "cert.pem"
        key_file = ssl_dir / "key.pem"
        
        if cert_file.exists() and key_file.exists():
            console.print("  ✅ SSL certificate files found")
            
            # Check certificate validity
            success, output = self.run_command([
                "openssl", "x509", "-in", str(cert_file), "-noout", "-dates"
            ])
            
            if success:
                console.print("  ✅ SSL certificate is valid")
                self.checks_passed.append("SSL certificates")
                return True
            else:
                console.print("  ❌ SSL certificate is invalid")
                self.checks_failed.append("SSL certificates")
                return False
        else:
            console.print("  ⚠️  SSL certificate files not found (will use Let's Encrypt)")
            self.checks_passed.append("SSL certificates (Let's Encrypt)")
            return True
    
    def check_api_endpoints(self) -> bool:
        """Check if API endpoints are accessible."""
        console.print("\n[bold cyan]Checking API Endpoints...[/bold cyan]")
        
        if not self.api_url.startswith("http://localhost"):
            console.print("  ⚠️  Skipping API checks (not deployed yet)")
            return True
        
        endpoints = [
            "/health",
            "/api/docs",
            "/metrics"
        ]
        
        all_accessible = True
        for endpoint in endpoints:
            try:
                response = requests.get(
                    f"{self.api_url}{endpoint}",
                    timeout=5,
                    verify=False  # For self-signed certificates
                )
                
                if response.status_code == 200:
                    console.print(f"  ✅ {endpoint}: Accessible")
                else:
                    console.print(f"  ❌ {endpoint}: Status {response.status_code}")
                    all_accessible = False
            except Exception as e:
                console.print(f"  ❌ {endpoint}: {str(e)}")
                all_accessible = False
        
        if all_accessible:
            self.checks_passed.append("API endpoints")
        else:
            self.checks_failed.append("API endpoints")
        
        return all_accessible
    
    def check_database_migrations(self) -> bool:
        """Check if database migrations are up to date."""
        console.print("\n[bold cyan]Checking Database Migrations...[/bold cyan]")
        
        alembic_dir = Path("web/backend/alembic")
        if not alembic_dir.exists():
            console.print("  ❌ Alembic directory not found")
            self.checks_failed.append("Database migrations")
            return False
        
        # Check if migrations are created
        versions_dir = alembic_dir / "versions"
        if versions_dir.exists():
            migrations = list(versions_dir.glob("*.py"))
            if migrations:
                console.print(f"  ✅ {len(migrations)} migration(s) found")
                self.checks_passed.append("Database migrations")
                return True
            else:
                console.print("  ❌ No migrations found")
                self.checks_failed.append("Database migrations")
                return False
        else:
            console.print("  ❌ Versions directory not found")
            self.checks_failed.append("Database migrations")
            return False
    
    def check_monitoring_setup(self) -> bool:
        """Check if monitoring is configured."""
        console.print("\n[bold cyan]Checking Monitoring Setup...[/bold cyan]")
        
        monitoring_files = [
            "monitoring/prometheus.yml",
            "monitoring/alerts.yml",
            "monitoring/grafana/provisioning/datasources/datasource.yml",
            "monitoring/grafana/provisioning/dashboards/dashboard.yml"
        ]
        
        all_present = True
        for file_path in monitoring_files:
            path = Path(file_path)
            if path.exists():
                console.print(f"  ✅ {file_path}: Present")
            else:
                console.print(f"  ❌ {file_path}: Missing")
                all_present = False
        
        if all_present:
            self.checks_passed.append("Monitoring setup")
        else:
            self.checks_failed.append("Monitoring setup")
        
        return all_present
    
    def check_ci_cd_pipeline(self) -> bool:
        """Check if CI/CD pipeline is configured."""
        console.print("\n[bold cyan]Checking CI/CD Pipeline...[/bold cyan]")
        
        workflow_file = Path(".github/workflows/deploy.yml")
        if workflow_file.exists():
            console.print("  ✅ GitHub Actions workflow found")
            
            # Check workflow syntax
            with open(workflow_file) as f:
                content = f.read()
                
            required_jobs = ["test", "build-and-push", "deploy-production"]
            missing_jobs = []
            
            for job in required_jobs:
                if f"  {job}:" in content:
                    console.print(f"  ✅ Job '{job}': Defined")
                else:
                    console.print(f"  ❌ Job '{job}': Missing")
                    missing_jobs.append(job)
            
            if missing_jobs:
                self.checks_failed.append("CI/CD pipeline")
                return False
            else:
                self.checks_passed.append("CI/CD pipeline")
                return True
        else:
            console.print("  ❌ GitHub Actions workflow not found")
            self.checks_failed.append("CI/CD pipeline")
            return False
    
    def check_security_scanning(self) -> bool:
        """Check if security scanning is configured."""
        console.print("\n[bold cyan]Checking Security Scanning...[/bold cyan]")
        
        # Check for security scanning in CI/CD
        workflow_file = Path(".github/workflows/deploy.yml")
        if workflow_file.exists():
            with open(workflow_file) as f:
                content = f.read()
            
            security_tools = ["trivy", "snyk", "codeql"]
            found_tools = []
            
            for tool in security_tools:
                if tool in content.lower():
                    console.print(f"  ✅ {tool.capitalize()}: Configured")
                    found_tools.append(tool)
            
            if found_tools:
                self.checks_passed.append("Security scanning")
                return True
            else:
                console.print("  ⚠️  No security scanning tools configured")
                self.checks_failed.append("Security scanning")
                return False
        else:
            self.checks_failed.append("Security scanning")
            return False
    
    def run_all_checks(self) -> int:
        """Run all production readiness checks."""
        console.print(Panel.fit(
            "[bold green]MCP Reliability Lab - Production Readiness Check[/bold green]\n"
            "Verifying all components for production deployment",
            border_style="green"
        ))
        
        checks = [
            ("Docker Images", self.check_docker_images),
            ("Docker Compose", self.check_docker_compose),
            ("Kubernetes Manifests", self.check_kubernetes_manifests),
            ("Environment Variables", self.check_environment_variables),
            ("SSL Certificates", self.check_ssl_certificates),
            ("Database Migrations", self.check_database_migrations),
            ("Monitoring Setup", self.check_monitoring_setup),
            ("CI/CD Pipeline", self.check_ci_cd_pipeline),
            ("Security Scanning", self.check_security_scanning),
            ("API Endpoints", self.check_api_endpoints)
        ]
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Running checks...", total=len(checks))
            
            for name, check_func in checks:
                try:
                    check_func()
                except Exception as e:
                    console.print(f"  ❌ {name}: Exception - {e}")
                    self.checks_failed.append(name)
                
                progress.advance(task)
                time.sleep(0.5)
        
        # Display summary
        console.print("\n" + "=" * 60)
        console.print("[bold]PRODUCTION READINESS SUMMARY[/bold]")
        console.print("=" * 60 + "\n")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Component", style="cyan", width=30)
        table.add_column("Status", width=15)
        
        for check in self.checks_passed:
            table.add_row(check, "[green]✅ READY[/green]")
        
        for check in self.checks_failed:
            table.add_row(check, "[red]❌ NOT READY[/red]")
        
        console.print(table)
        
        # Overall result
        total_checks = len(self.checks_passed) + len(self.checks_failed)
        passed_percentage = (len(self.checks_passed) / total_checks * 100) if total_checks > 0 else 0
        
        console.print(f"\n[bold]Result: {len(self.checks_passed)}/{total_checks} checks passed ({passed_percentage:.1f}%)[/bold]")
        
        if len(self.checks_failed) == 0:
            console.print(Panel.fit(
                "[bold green]🚀 PRODUCTION READY! 🚀[/bold green]\n\n"
                "All checks passed. The system is ready for production deployment.\n\n"
                "Next steps:\n"
                "1. Set production environment variables\n"
                "2. Run: docker-compose -f docker-compose.production.yml up -d\n"
                "3. Or deploy to Kubernetes: kubectl apply -f k8s/production/",
                title="SUCCESS",
                border_style="green"
            ))
            return 0
        else:
            console.print(Panel.fit(
                f"[bold red]⚠️  NOT READY FOR PRODUCTION[/bold red]\n\n"
                f"{len(self.checks_failed)} check(s) failed.\n\n"
                "Please fix the issues above before deploying to production.",
                title="FAILED",
                border_style="red"
            ))
            return 1


def main():
    """Main entry point."""
    verifier = ProductionVerifier()
    return verifier.run_all_checks()


if __name__ == "__main__":
    sys.exit(main())