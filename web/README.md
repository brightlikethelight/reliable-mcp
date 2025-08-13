# MCP Reliability Lab Web Dashboard

Real-time monitoring and testing dashboard for MCP (Model Context Protocol) servers.

## Features

### Backend (FastAPI)
- **REST API**: Complete CRUD operations for tests, results, metrics, servers, and reports
- **WebSocket Support**: Real-time updates for logs, metrics, and events
- **Authentication**: JWT-based authentication with OAuth2
- **Rate Limiting**: Configurable rate limiting with Redis/in-memory fallback
- **Background Tasks**: Scheduled test runs and report generation
- **Caching**: Redis-based caching with fallback to in-memory storage

### Frontend (Next.js 14 + TypeScript)
- **Dashboard Overview**: Real-time metrics and status monitoring
- **Test Management**: Create, run, and monitor test suites
- **Performance Benchmarks**: Compare metrics across configurations
- **Analytics**: Time-series charts, heatmaps, and reliability scoring
- **Real-time Updates**: WebSocket integration for live data streaming
- **Dark Mode**: Built-in dark mode support

## Quick Start

### Using the Startup Script

```bash
# Make the script executable (first time only)
chmod +x start.sh

# Start both backend and frontend
./start.sh
```

The script will:
1. Install all dependencies
2. Start the FastAPI backend on http://localhost:8000
3. Start the Next.js frontend on http://localhost:3000
4. Handle graceful shutdown on Ctrl+C

### Manual Setup

#### Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the backend
python main.py
```

Backend will be available at:
- API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- WebSocket: ws://localhost:8000/ws

#### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

Frontend will be available at http://localhost:3000

## Architecture

```
web/
├── backend/               # FastAPI backend
│   ├── api/              # REST API endpoints
│   ├── core/             # Core functionality (auth, config, database)
│   ├── schemas/          # Pydantic models
│   ├── services/         # Business logic
│   └── websocket/        # WebSocket handlers
├── frontend/             # Next.js frontend
│   ├── app/             # Next.js 14 app directory
│   ├── components/      # React components
│   ├── hooks/           # Custom React hooks
│   └── stores/          # Zustand state management
└── start.sh             # Startup script

```

## API Endpoints

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/refresh` - Refresh JWT token
- `GET /api/auth/me` - Get current user

### Tests
- `GET /api/tests` - List all tests
- `POST /api/tests` - Create new test
- `GET /api/tests/{id}` - Get test details
- `POST /api/tests/run` - Run test suite
- `DELETE /api/tests/{id}` - Delete test

### Metrics
- `GET /api/metrics` - Get metrics
- `GET /api/metrics/summary` - Get metrics summary
- `POST /api/metrics` - Record new metrics

### Servers
- `GET /api/servers` - List all servers
- `POST /api/servers/{id}/start` - Start server
- `POST /api/servers/{id}/stop` - Stop server
- `GET /api/servers/{id}/health` - Check server health

### WebSocket Channels
- `/ws/logs` - Real-time log streaming
- `/ws/metrics` - Real-time metrics updates
- `/ws/events` - Real-time event notifications

## Configuration

### Backend Configuration

Edit `backend/core/config.py` or set environment variables:

```env
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:pass@localhost/db
REDIS_URL=redis://localhost:6379/0
RATE_LIMIT_PER_MINUTE=60
```

### Frontend Configuration

Edit `frontend/next.config.js` for API proxy settings.

## Development

### Backend Development

```bash
cd backend
# Run with hot reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development

```bash
cd frontend
# Run with hot reload
npm run dev
```

### Running Tests

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

## Production Deployment

### Backend
```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Frontend
```bash
cd frontend
npm run build
npm start
```

## Troubleshooting

### Port Already in Use
If ports 3000 or 8000 are already in use:
```bash
# Find process using port
lsof -i :3000
lsof -i :8000

# Kill process
kill -9 <PID>
```

### Dependencies Issues
```bash
# Backend: Reinstall dependencies
cd backend
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend: Reinstall dependencies
cd frontend
rm -rf node_modules package-lock.json
npm install
```

## License

MIT