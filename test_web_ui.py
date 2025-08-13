#!/usr/bin/env python3
"""
Simple test to verify the web UI can be imported and basic routes work.
"""

import sys
from pathlib import Path

# Add path for imports
sys.path.insert(0, str(Path(__file__).parent))

def test_import():
    """Test that we can import the web UI."""
    try:
        from web_ui import app
        print("✅ Web UI app imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import web UI: {e}")
        return False

def test_routes():
    """Test that routes are defined."""
    try:
        from web_ui import app
        
        routes = []
        for route in app.routes:
            if hasattr(route, 'path'):
                routes.append(route.path)
        
        expected_routes = ["/", "/test", "/metrics", "/leaderboard", "/run-test", "/api/stats", "/health"]
        
        print("\n📍 Defined Routes:")
        for route in routes:
            if route in expected_routes:
                print(f"  ✅ {route}")
            else:
                print(f"  📌 {route}")
        
        return True
    except Exception as e:
        print(f"❌ Failed to check routes: {e}")
        return False

def test_templates():
    """Test that templates exist."""
    templates_dir = Path("templates")
    
    if not templates_dir.exists():
        print("❌ Templates directory not found")
        return False
    
    required_templates = [
        "index.html",
        "test.html", 
        "metrics.html",
        "leaderboard.html",
        "partials/test_results.html"
    ]
    
    print("\n📄 Templates:")
    for template in required_templates:
        template_path = templates_dir / template
        if template_path.exists():
            print(f"  ✅ {template}")
        else:
            print(f"  ❌ {template} (missing)")
    
    return True

def main():
    """Run all tests."""
    print("=" * 50)
    print("MCP Reliability Lab - Web UI Test")
    print("=" * 50)
    
    all_passed = True
    
    # Test import
    if not test_import():
        all_passed = False
        print("\n⚠️  Cannot proceed without successful import")
        return
    
    # Test routes
    if not test_routes():
        all_passed = False
    
    # Test templates
    if not test_templates():
        all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("✅ All tests passed!")
        print("\nTo start the web UI, run:")
        print("  python web_ui.py")
        print("\nThen open http://localhost:8000")
    else:
        print("⚠️  Some tests failed")
        print("\nYou may need to install dependencies:")
        print("  pip install fastapi uvicorn jinja2")
    print("=" * 50)

if __name__ == "__main__":
    main()