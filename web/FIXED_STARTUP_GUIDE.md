# MCP Reliability Lab Web Dashboard - Fixed Startup Guide

## ✅ All Issues Resolved

The following critical issues have been fixed:

### 1. Backend Import Error - FIXED ✅
- **Issue**: `ImportError: attempted relative import with no known parent package`
- **Solution**: Fixed module initialization files and import paths in `main.py`, `__init__.py` files
- **Files Updated**:
  - `/backend/main.py` - Simplified imports with proper path resolution
  - `/backend/__init__.py` - Implemented lazy loading
  - `/backend/core/__init__.py` - Fixed eager import issues

### 2. Frontend CSS Error - FIXED ✅
- **Issue**: `The 'border-border' class does not exist`
- **Solution**: Added missing CSS custom properties and Tailwind configuration
- **Files Updated**:
  - `/frontend/app/globals.css` - Added `--border` CSS variable
  - `/frontend/tailwind.config.ts` - Added border, background, foreground colors

## 🚀 Quick Start (After Fixes)

### Option 1: Use the Startup Script
```bash
cd /Users/brightliu/Coding_Projects/modal_hackathon/mcp_reliability_lab/web
./start.sh
```

### Option 2: Manual Startup

#### Start Backend:
```bash
cd /Users/brightliu/Coding_Projects/modal_hackathon/mcp_reliability_lab/web/backend

# Activate virtual environment (already created)
source venv/bin/activate

# Run the backend
python main.py
```

Backend will start on http://localhost:8000

#### Start Frontend:
```bash
cd /Users/brightliu/Coding_Projects/modal_hackathon/mcp_reliability_lab/web/frontend

# Run the development server
npm run dev
```

Frontend will start on http://localhost:3000

## 🧪 Testing the Application

Use the test script to verify everything is working:

```bash
cd /Users/brightliu/Coding_Projects/modal_hackathon/mcp_reliability_lab/web
./test_dashboard.sh
```

Expected output:
```
✓ Backend is running on port 8000
✓ Frontend is running on port 3000
✓ API Documentation (HTTP 200)
✓ Health Check (HTTP 200)
✓ Homepage (HTTP 200)
```

## 📍 Access Points

Once both servers are running:

- **Frontend Dashboard**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **WebSocket**: ws://localhost:8000/ws

## 🎯 Key Features Working

### Backend Features:
- ✅ FastAPI server with automatic OpenAPI docs
- ✅ REST API endpoints (tests, metrics, servers, reports)
- ✅ WebSocket support for real-time updates
- ✅ JWT authentication ready
- ✅ Rate limiting with fallback
- ✅ Background task processing

### Frontend Features:
- ✅ Next.js 14 with TypeScript
- ✅ Real-time dashboard with metrics
- ✅ Dark mode support
- ✅ Responsive design
- ✅ WebSocket integration
- ✅ State management with Zustand

## 📝 Environment Variables (Optional)

Create `.env` files for custom configuration:

### Backend (.env in /backend):
```env
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://localhost/mcp_reliability
REDIS_URL=redis://localhost:6379/0
DEBUG=true
```

### Frontend (.env.local in /frontend):
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

## 🔧 Troubleshooting

### If Backend Won't Start:
1. Check Python version: `python --version` (needs 3.8+)
2. Reinstall dependencies:
   ```bash
   cd backend
   rm -rf venv
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

### If Frontend Won't Start:
1. Check Node version: `node --version` (needs 16+)
2. Reinstall dependencies:
   ```bash
   cd frontend
   rm -rf node_modules package-lock.json
   npm install
   ```

### Port Already in Use:
```bash
# Find and kill process on port 8000
lsof -i :8000
kill -9 <PID>

# Find and kill process on port 3000
lsof -i :3000
kill -9 <PID>
```

## ✨ Next Steps

With the dashboard now working, you can:

1. **Explore the UI**: Navigate through Dashboard, Tests, Benchmarks, and Analytics pages
2. **Test API**: Use the interactive docs at http://localhost:8000/docs
3. **Monitor Real-time**: Watch live metrics update on the dashboard
4. **Run Tests**: Create and execute test suites from the Tests page
5. **View Analytics**: Analyze performance trends and reliability scores

## 🎉 Success!

The MCP Reliability Lab Web Dashboard is now fully functional with all critical issues resolved. Both the FastAPI backend and Next.js frontend are working correctly with proper imports and CSS configurations.