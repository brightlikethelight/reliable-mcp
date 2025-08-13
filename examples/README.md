# MCP Reliability Lab Examples

This directory contains practical examples demonstrating how to use the MCP Reliability Lab for testing Model Context Protocol servers.

## 📚 Available Examples

### 01_basic_test.py
**Basic MCP Server Test**
- Connect to an MCP server
- List available tools
- Perform basic file operations
- Calculate simple metrics

```bash
python examples/01_basic_test.py
```

### 02_scientific_testing.py
**Scientific Testing Suite**
- Property-based testing with random inputs
- Chaos engineering with fault injection
- Complete scientific test suite
- Edge case handling

```bash
python examples/02_scientific_testing.py
```

### 03_benchmarking.py
**Performance Benchmarking**
- Standard workload benchmarks
- Custom workload creation
- Workload comparison
- Leaderboard updates

```bash
python examples/03_benchmarking.py
```

### 04_server_comparison.py
**Multi-Server Comparison**
- Compare multiple MCP servers
- Head-to-head testing
- Stress test comparison
- Performance rankings

```bash
python examples/04_server_comparison.py
```

### 05_integration.py
**Application Integration**
- Client wrapper for easy integration
- Automated testing examples
- Monitoring and alerting
- Custom use cases

```bash
python examples/05_integration.py
```

## 🚀 Getting Started

### Prerequisites

1. Install MCP Reliability Lab:
```bash
cd ..
./install.sh
```

2. Activate virtual environment:
```bash
source venv/bin/activate
```

3. Ensure MCP servers are installed:
```bash
npm install -g @modelcontextprotocol/server-filesystem
```

### Running Examples

Each example is self-contained and can be run directly:

```bash
# Run a specific example
python examples/01_basic_test.py

# Run all examples
for example in examples/*.py; do
    echo "Running $example..."
    python "$example"
done
```

## 📝 Example Structure

Each example follows this structure:

1. **Imports** - Required modules and path setup
2. **Functions** - Specific test demonstrations
3. **Main** - Entry point with error handling
4. **Summary** - What was demonstrated and next steps

## 🔧 Customization

### Modifying Server Configuration

Edit the server configuration in any example:

```python
server_config = {
    "name": "your_server",
    "type": "your_type",
    "path": "/your/path"
}
```

### Adjusting Test Parameters

Modify workload duration and parameters:

```python
workload.duration_seconds = 60  # Longer test
workload.weights = {
    "read": 0.6,   # 60% reads
    "write": 0.4   # 40% writes
}
```

### Creating Custom Workloads

Define your own workload class:

```python
class CustomWorkload(Workload):
    def __init__(self):
        super().__init__(
            name="custom",
            description="My custom workload",
            duration_seconds=30,
            weights={"operation": 1.0}
        )
```

## 📊 Understanding Output

### Metrics Explained

- **Throughput**: Operations per second (higher is better)
- **Latency P95**: 95% of requests complete within this time (lower is better)
- **Consistency**: How predictable the performance is (higher is better)
- **Error Rate**: Percentage of failed operations (lower is better)

### Score Interpretation

- **90-100**: Excellent, production ready
- **70-89**: Good, minor improvements needed
- **50-69**: Fair, significant improvements needed
- **0-49**: Poor, not recommended for production

## 🐛 Troubleshooting

### Common Issues

**Import Error**
```python
# Ensure you're in the examples directory
cd examples
python 01_basic_test.py
```

**Server Not Found**
```bash
# Install the required MCP server
npm install -g @modelcontextprotocol/server-filesystem
```

**Permission Denied**
```bash
# Use a writable directory
mkdir -p /tmp/mcp-test
chmod 755 /tmp/mcp-test
```

**Database Locked**
```bash
# Clean up old database files
rm ../*.db
python ../init_database.py
```

## 📚 Learning Path

1. Start with `01_basic_test.py` to understand the basics
2. Move to `02_scientific_testing.py` for advanced testing
3. Try `03_benchmarking.py` for performance analysis
4. Use `04_server_comparison.py` to compare servers
5. Integrate with `05_integration.py` in your projects

## 🤝 Contributing

To add a new example:

1. Create a new file: `examples/06_your_example.py`
2. Follow the existing structure
3. Add clear comments and documentation
4. Update this README
5. Submit a pull request

## 📄 License

These examples are part of the MCP Reliability Lab project and are licensed under the MIT License.