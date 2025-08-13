#!/bin/bash
# verify_all_claims.sh - Comprehensive verification of MCP Reliability Lab

echo "================================"
echo "MCP RELIABILITY LAB VERIFICATION"
echo "================================"

PASS="✅"
FAIL="❌"
RESULTS=()

# Function to test and record result
test_claim() {
    local name=$1
    local command=$2
    echo -n "Testing: $name... "
    if eval $command > /dev/null 2>&1; then
        echo "$PASS"
        RESULTS+=("$PASS $name")
        return 0
    else
        echo "$FAIL"
        RESULTS+=("$FAIL $name")
        return 1
    fi
}

# 1. DOCKER TESTS
echo -e "\n1. DOCKER CONFIGURATION"
test_claim "Backend Dockerfile exists" "[ -f web/backend/Dockerfile ]"
test_claim "Frontend Dockerfile exists" "[ -f web/frontend/Dockerfile ]"
test_claim "Docker Compose Production exists" "[ -f docker-compose.production.yml ]"
test_claim "Backend Docker builds" "cd web/backend && docker build -t test-backend . --no-cache"
test_claim "Frontend Docker builds" "cd web/frontend && docker build -t test-frontend . --no-cache"
test_claim "Docker Compose config valid" "docker-compose -f docker-compose.production.yml config"

# 2. KUBERNETES TESTS
echo -e "\n2. KUBERNETES MANIFESTS"
test_claim "K8s directory exists" "[ -d k8s/production ]"
test_claim "Namespace manifest exists" "[ -f k8s/production/00-namespace.yaml ]"
test_claim "K8s manifests valid" "kubectl apply --dry-run=client -f k8s/production/ 2>/dev/null"
test_claim "Has StatefulSet for DB" "grep -q StatefulSet k8s/production/* 2>/dev/null"
test_claim "Has HPA for scaling" "grep -q HorizontalPodAutoscaler k8s/production/* 2>/dev/null"
test_claim "Has Ingress configured" "grep -q Ingress k8s/production/* 2>/dev/null"

# 3. CI/CD TESTS
echo -e "\n3. CI/CD PIPELINE"
test_claim "GitHub Actions workflow exists" "[ -f .github/workflows/deploy.yml ]"
test_claim "Has test job" "grep -q 'jobs:.*test:' .github/workflows/deploy.yml 2>/dev/null"
test_claim "Has build job" "grep -q 'docker.*build' .github/workflows/deploy.yml 2>/dev/null"
test_claim "Has security scanning" "grep -q 'trivy\|snyk' .github/workflows/deploy.yml 2>/dev/null"
test_claim "Has deployment steps" "grep -q 'kubectl.*apply' .github/workflows/deploy.yml 2>/dev/null"

# 4. DATABASE TESTS
echo -e "\n4. DATABASE FUNCTIONALITY"
test_claim "Database models exist" "[ -d web/backend/models ]"
test_claim "Alembic migrations exist" "[ -d web/backend/alembic/versions ]"
test_claim "Database config exists" "[ -f web/backend/core/database.py ]"
test_claim "User model exists" "[ -f web/backend/models/user.py ]"
test_claim "Server model exists" "[ -f web/backend/models/server.py ]"

# 5. API TESTS
echo -e "\n5. API FUNCTIONALITY"
test_claim "FastAPI main exists" "[ -f web/backend/main.py ]"
test_claim "Auth API exists" "[ -f web/backend/api/auth.py ]"
test_claim "Server API exists" "[ -f web/backend/api/servers.py ]"
test_claim "Test API exists" "[ -f web/backend/api/tests.py ]"
test_claim "WebSocket handler exists" "[ -f web/backend/websocket/handlers.py ]"

# 6. FRONTEND TESTS
echo -e "\n6. FRONTEND FUNCTIONALITY"
cd web/frontend 2>/dev/null
test_claim "Package.json exists" "[ -f package.json ]"
test_claim "Next.js app directory exists" "[ -d app ]"
test_claim "Components directory exists" "[ -d components ]"
test_claim "TypeScript config exists" "[ -f tsconfig.json ]"
test_claim "Has dashboard component" "[ -f components/dashboard/dashboard.tsx ]"
test_claim "Has test components" "[ -d components/tests ]"
cd ../.. 2>/dev/null

# 7. MCP INTEGRATION TESTS
echo -e "\n7. MCP INTEGRATION"
test_claim "MCP client exists" "[ -f web/backend/core/mcp_client.py ]"
test_claim "MCP servers config exists" "[ -f web/backend/core/mcp_servers.py ]"
test_claim "Real test runner exists" "[ -f web/backend/services/real_test_runner.py ]"
test_claim "MCP client has transports" "grep -q 'StdioTransport\|HttpTransport\|WebSocketTransport' web/backend/core/mcp_client.py"
test_claim "Has JSON-RPC implementation" "grep -q 'jsonrpc.*2.0' web/backend/core/mcp_client.py"

# 8. CLI TESTS
echo -e "\n8. CLI FUNCTIONALITY"
test_claim "CLI main exists" "[ -f mcp_reliability_cli.py ]"
test_claim "Has test command" "grep -q '@click.command.*test' mcp_reliability_cli.py 2>/dev/null || grep -q 'def test' mcp_reliability_cli.py 2>/dev/null"
test_claim "Has benchmark command" "grep -q '@click.command.*benchmark' mcp_reliability_cli.py 2>/dev/null || grep -q 'def benchmark' mcp_reliability_cli.py 2>/dev/null"
test_claim "Has server command" "grep -q '@click.command.*server' mcp_reliability_cli.py 2>/dev/null || grep -q 'def server' mcp_reliability_cli.py 2>/dev/null"

# 9. MONITORING TESTS
echo -e "\n9. MONITORING SETUP"
test_claim "Prometheus config exists" "[ -f monitoring/prometheus.yml ]"
test_claim "Grafana directory exists" "[ -d monitoring/grafana ]"
test_claim "Alert rules exist" "[ -f monitoring/alerts.yml ]"
test_claim "Has Prometheus in docker-compose" "grep -q 'prometheus' docker-compose.production.yml"

# 10. SECURITY TESTS
echo -e "\n10. SECURITY MEASURES"
test_claim "Uses non-root in Backend Docker" "grep -q 'USER.*[^root]' web/backend/Dockerfile 2>/dev/null"
test_claim "Uses non-root in Frontend Docker" "grep -q 'USER.*[^root]' web/frontend/Dockerfile 2>/dev/null"
test_claim "Has .env template" "[ -f .env.production.template ]"
test_claim "Security module exists" "[ -f web/backend/core/security.py ]"
test_claim "JWT implementation exists" "grep -q 'jwt\|JWT' web/backend/core/security.py"

# 11. TESTING INFRASTRUCTURE
echo -e "\n11. TESTING INFRASTRUCTURE"
test_claim "Backend tests exist" "[ -d tests ]"
test_claim "Integration tests exist" "[ -d tests/integration ]"
test_claim "E2E test exists" "[ -f tests/integration/test_e2e_complete_flow.py ]"
test_claim "Real MCP test exists" "[ -f tests/integration/test_real_mcp_execution.py ]"

# 12. PRODUCTION READINESS
echo -e "\n12. PRODUCTION READINESS"
test_claim "Has Makefile" "[ -f Makefile ]"
test_claim "Has deployment guide" "[ -f DEPLOYMENT_GUIDE.md ]"
test_claim "Has production verification" "[ -f verify_production.py ]"
test_claim "Has rate limiting" "[ -f web/backend/core/rate_limiter.py ]"
test_claim "Has Redis config" "[ -f web/backend/core/redis.py ]"

# 13. ACTUAL FUNCTIONALITY TESTS
echo -e "\n13. ACTUAL FUNCTIONALITY (CRITICAL)"
test_claim "Python imports work" "cd web/backend && python -c 'from main import app' 2>/dev/null"
test_claim "Database imports work" "cd web/backend && python -c 'from core.database import get_db' 2>/dev/null"
test_claim "MCP client imports" "cd web/backend && python -c 'from core.mcp_client import MCPClient' 2>/dev/null"
test_claim "Frontend builds" "cd web/frontend && npm run build 2>/dev/null"

# SUMMARY
echo -e "\n================================"
echo "VERIFICATION SUMMARY"
echo "================================"
PASSED=0
FAILED=0
for result in "${RESULTS[@]}"; do
    echo "$result"
    if [[ $result == *"✅"* ]]; then
        ((PASSED++))
    else
        ((FAILED++))
    fi
done

TOTAL=$((PASSED + FAILED))
PERCENTAGE=$((PASSED * 100 / TOTAL))

echo -e "\nTOTAL: $PASSED/$TOTAL passed ($PERCENTAGE%)"

if [ $FAILED -eq 0 ]; then
    echo "ALL CLAIMS VERIFIED!"
else
    echo "WARNING: $FAILED claims could not be verified"
    echo "The system may not be fully functional as described"
fi

# Critical functionality check
echo -e "\n================================"
echo "CRITICAL FUNCTIONALITY CHECK"
echo "================================"

if [ $PERCENTAGE -lt 50 ]; then
    echo "CRITICAL: Less than 50% of claims verified!"
    echo "This suggests the system is largely non-functional"
elif [ $PERCENTAGE -lt 75 ]; then
    echo "WARNING: Only $PERCENTAGE% verified"
    echo "Significant functionality may be missing"
elif [ $PERCENTAGE -lt 90 ]; then
    echo "NOTICE: $PERCENTAGE% verified"
    echo "Most features present but some gaps exist"
else
    echo "GOOD: $PERCENTAGE% verified"
    echo "System appears to be mostly functional"
fi