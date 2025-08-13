#!/bin/bash

# Deploy MCP Reliability Lab to Modal
# This script deploys our entire testing framework to Modal's serverless infrastructure

echo "🚀 MCP Reliability Lab - Modal Deployment"
echo "=========================================="
echo ""

# Check if Modal is installed
if ! command -v modal &> /dev/null; then
    echo "❌ Modal CLI not found. Installing..."
    pip install modal
else
    echo "✅ Modal CLI found"
fi

# Authenticate with Modal (if needed)
echo "🔐 Checking Modal authentication..."
modal token id &> /dev/null
if [ $? -ne 0 ]; then
    echo "Please authenticate with Modal:"
    modal token new
fi

echo ""
echo "📦 Deploying applications to Modal..."
echo ""

# Deploy main testing framework
echo "1️⃣ Deploying main MCP testing framework..."
modal deploy modal_app.py
if [ $? -eq 0 ]; then
    echo "   ✅ Main framework deployed successfully"
else
    echo "   ❌ Failed to deploy main framework"
    exit 1
fi

# Deploy self-testing agent
echo ""
echo "2️⃣ Deploying Self-Testing Agent..."
modal deploy agents/self_testing_agent.py
if [ $? -eq 0 ]; then
    echo "   ✅ Self-Testing Agent deployed"
else
    echo "   ❌ Failed to deploy Self-Testing Agent"
fi

# Deploy reliability oracle
echo ""
echo "3️⃣ Deploying Reliability Oracle..."
modal deploy agents/reliability_oracle.py
if [ $? -eq 0 ]; then
    echo "   ✅ Reliability Oracle deployed"
else
    echo "   ❌ Failed to deploy Reliability Oracle"
fi

echo ""
echo "🌐 Getting deployment URLs..."
echo ""

# Get dashboard URL
DASHBOARD_URL=$(modal app list | grep mcp-dashboard | awk '{print $NF}')
if [ ! -z "$DASHBOARD_URL" ]; then
    echo "📊 Dashboard URL: https://$DASHBOARD_URL"
else
    echo "📊 Dashboard URL: Check https://modal.com/apps"
fi

echo ""
echo "🎯 Deployment Complete!"
echo ""
echo "Available endpoints:"
echo "  • Dashboard: https://your-username--mcp-dashboard.modal.run"
echo "  • Self-Testing Agent: via Modal functions"
echo "  • Reliability Oracle: via Modal functions"
echo ""
echo "To test the deployment, run:"
echo "  modal run modal_app.py::massive_parallel_test --server-urls '[\"https://httpbin.org\"]'"
echo ""
echo "To view logs:"
echo "  modal app logs mcp-reliability-lab"
echo ""
echo "To run scheduled scans:"
echo "  The system will automatically scan servers every hour"
echo ""
echo "🏆 Ready for the hackathon!"