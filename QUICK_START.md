# 🚀 MCP Reliability Lab - Quick Start Guide

Get up and running in **under 5 minutes**!

## 1️⃣ One-Command Install

```bash
curl -sSL https://raw.githubusercontent.com/yourusername/mcp-reliability-lab/main/install.sh | bash
```

Or if you've cloned the repo:
```bash
./install.sh
```

## 2️⃣ Start the Lab

```bash
cd ~/mcp-reliability-lab
./start.sh
```

Open http://localhost:8000 in your browser!

## 3️⃣ Your First Test

### Option A: Web UI
1. Open http://localhost:8000
2. Click "New Test"
3. Select "filesystem" server
4. Click "Run Test"
5. Watch real-time results!

### Option B: CLI
```bash
# Basic test
./mcp-lab test filesystem

# Scientific test suite
./mcp-lab test filesystem --scientific

# Benchmark
./mcp-lab benchmark filesystem --duration 30

# Compare servers
./mcp-lab compare filesystem github
```

## 4️⃣ Understanding Results

### Reliability Score (0-100)
- **90-100**: Production ready 🟢
- **70-89**: Mostly stable 🟡
- **50-69**: Needs work 🟠
- **0-49**: Not recommended 🔴

### Key Metrics
- **Throughput**: Operations per second
- **Latency P95**: 95% of requests complete within this time
- **Consistency**: How predictable the performance is (higher is better)
- **Error Rate**: Percentage of failed operations

## 5️⃣ Common Commands

```bash
# View leaderboard
./mcp-lab leaderboard

# Generate HTML report
./mcp-lab report --format html --output report.html

# Run specific workload
./mcp-lab benchmark filesystem --workload crud_heavy

# Start web server on different port
./mcp-lab start --port 8080
```

## 6️⃣ Docker Quick Start

```bash
# Using Docker Compose
docker-compose up

# Using Docker directly
docker build -t mcp-lab .
docker run -p 8000:8000 mcp-lab

# With PostgreSQL and Redis
docker-compose --profile with-postgres --profile with-redis up
```

## 7️⃣ Testing Your Own MCP Server

### Add to config
```python
# In mcp_client_expanded.py
SERVERS = {
    "myserver": {
        "command": ["node", "/path/to/your/server.js"],
        "args": ["--config", "/path/to/config.json"]
    }
}
```

### Test it
```bash
./mcp-lab test myserver --scientific
./mcp-lab benchmark myserver
```

## 📊 Available Workloads

- **real_world_mix**: Balanced mix of operations
- **crud_heavy**: Create, Read, Update, Delete focus
- **read_intensive**: 80% read operations
- **write_intensive**: 70% write operations
- **search_heavy**: Complex queries and searches
- **concurrent_stress**: High concurrency testing
- **large_operations**: Big file/data operations

## 🎯 Test Types

### Basic Test
Quick smoke test with 3 operations (write, read, list)

### Scientific Test Suite
- **Property Testing**: Random input generation
- **State Machine**: Stateful operation sequences
- **Chaos Testing**: Fault injection (errors, latency)
- **Performance**: Throughput and latency analysis
- **Consistency**: Variation analysis

### Benchmarking
- Configurable duration (default 30s)
- Standard workload patterns
- Real-time metrics collection
- Automatic leaderboard updates

## 🔧 Configuration

### Environment Variables
```bash
export MCP_LAB_PORT=8000
export MCP_LAB_HOST=0.0.0.0
export MCP_LAB_DB_PATH=/path/to/databases
export MCP_LAB_TEST_PATH=/tmp/mcp-tests
```

### Settings File
Create `~/.mcp-lab/config.json`:
```json
{
  "default_duration": 60,
  "default_workload": "real_world_mix",
  "auto_report": true,
  "report_format": "html"
}
```

## 📈 Advanced Usage

### Custom Workloads
```python
# Create workloads/custom.py
from benchmarking.workloads import Workload

class MyWorkload(Workload):
    def __init__(self):
        super().__init__(
            name="my_custom",
            description="My custom workload",
            weights={
                "read": 0.5,
                "write": 0.3,
                "list": 0.2
            }
        )
```

### Automation
```bash
# Continuous testing
while true; do
  ./mcp-lab test filesystem
  sleep 300  # Test every 5 minutes
done

# Daily benchmark
0 2 * * * cd ~/mcp-reliability-lab && ./mcp-lab benchmark filesystem --duration 300
```

### CI/CD Integration
```yaml
# GitHub Actions example
- name: Test MCP Server
  run: |
    ./install.sh
    ./mcp-lab test myserver --scientific
    ./mcp-lab report --format json --output results.json
    
- name: Check Results
  run: |
    score=$(jq '.scientific_score.overall_score' results.json)
    if (( $(echo "$score < 70" | bc -l) )); then
      echo "Score too low: $score"
      exit 1
    fi
```

## 🐛 Troubleshooting

### Port already in use
```bash
lsof -i :8000  # Find process
kill -9 <PID>  # Kill it
./start.sh     # Restart
```

### MCP server not found
```bash
# Reinstall MCP servers
npm install -g @modelcontextprotocol/server-filesystem
```

### Permission denied
```bash
chmod +x install.sh start.sh mcp-lab
```

### Database locked
```bash
rm *.db
python3 init_database.py
```

## 📚 Learn More

- [Full Documentation](https://docs.mcp-lab.com)
- [API Reference](https://docs.mcp-lab.com/api)
- [Contributing Guide](https://github.com/yourusername/mcp-reliability-lab/CONTRIBUTING.md)
- [Report Issues](https://github.com/yourusername/mcp-reliability-lab/issues)

## 💡 Tips

1. **Start simple**: Run basic tests before scientific suites
2. **Watch consistency**: High variation = unpredictable performance
3. **Compare fairly**: Use same workload and duration
4. **Check logs**: `tail -f mcp_test.log` for debugging
5. **Use filters**: Focus on specific metrics that matter

---

**Ready to test?** Run `./start.sh` and open http://localhost:8000! 🚀