# Contributing to MCP Reliability Lab

First off, thank you for considering contributing to MCP Reliability Lab! It's people like you that make MCP Reliability Lab such a great tool.

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to team@mcp-lab.com.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible:

* **Use a clear and descriptive title**
* **Describe the exact steps to reproduce the problem**
* **Provide specific examples to demonstrate the steps**
* **Describe the behavior you observed and expected**
* **Include logs and error messages**
* **Include your environment details** (OS, Python version, MCP server version)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, please include:

* **Use a clear and descriptive title**
* **Provide a detailed description of the suggested enhancement**
* **Provide specific examples to demonstrate the enhancement**
* **Describe the current behavior and expected behavior**
* **Explain why this enhancement would be useful**

### Your First Code Contribution

Unsure where to begin? You can start by looking through these issues:

* `good first issue` - issues which should only require a few lines of code
* `help wanted` - issues which should be a bit more involved
* `documentation` - issues related to improving documentation

### Pull Requests

1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes.
5. Make sure your code lints.
6. Issue that pull request!

## Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/mcp-reliability-lab.git
cd mcp-reliability-lab

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Install MCP servers for testing
npm install -g @modelcontextprotocol/server-filesystem

# Initialize databases
python init_database.py

# Run tests
pytest

# Run linting
black .
flake8
mypy .
```

## Development Process

### 1. Create a Feature Branch

```bash
git checkout -b feature/amazing-feature
```

### 2. Make Your Changes

Follow these coding standards:

#### Python Style
* Follow PEP 8
* Use type hints for all functions
* Maximum line length: 100 characters
* Use descriptive variable names
* Add docstrings to all public functions

Example:
```python
def calculate_reliability_score(
    success_count: int,
    total_count: int,
    weight: float = 1.0
) -> float:
    """
    Calculate reliability score based on success rate.
    
    Args:
        success_count: Number of successful operations
        total_count: Total number of operations
        weight: Optional weight factor (0.0-1.0)
    
    Returns:
        Reliability score between 0 and 100
    """
    if total_count == 0:
        return 0.0
    
    raw_score = (success_count / total_count) * 100
    return raw_score * weight
```

#### Testing
* Write tests for all new functionality
* Maintain test coverage above 80%
* Use descriptive test names
* Test edge cases

Example:
```python
def test_calculate_reliability_score_with_zero_total():
    """Test that zero total operations returns score of 0."""
    score = calculate_reliability_score(0, 0)
    assert score == 0.0

def test_calculate_reliability_score_perfect():
    """Test that all successful operations return score of 100."""
    score = calculate_reliability_score(10, 10)
    assert score == 100.0
```

### 3. Commit Your Changes

Use conventional commits:

* `feat:` New feature
* `fix:` Bug fix
* `docs:` Documentation changes
* `style:` Code style changes (formatting, etc)
* `refactor:` Code refactoring
* `test:` Adding or updating tests
* `chore:` Maintenance tasks

Example:
```bash
git commit -m "feat: add chaos testing for network failures"
```

### 4. Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=mcp_reliability_lab --cov-report=html

# Run specific test file
pytest tests/test_benchmark.py

# Run tests in parallel
pytest -n auto
```

### 5. Update Documentation

* Update README.md if needed
* Add/update docstrings
* Update CHANGELOG.md (we'll do this for you on release)
* Add examples if introducing new features

### 6. Push and Create PR

```bash
git push origin feature/amazing-feature
```

Then create a Pull Request on GitHub with:

* Clear title and description
* Reference any related issues
* Include screenshots for UI changes
* List any breaking changes

## Project Structure

```
mcp_reliability_lab/
├── mcp_client_*.py         # MCP client implementations
├── scientific_test_*.py    # Testing frameworks
├── benchmarking/           # Benchmarking module
│   ├── __init__.py
│   ├── benchmark_runner.py
│   ├── workloads.py
│   └── leaderboard.py
├── services/               # Service layer
│   ├── __init__.py
│   ├── test_runner_service.py
│   └── metrics_service.py
├── property_tests/         # Property-based tests
│   ├── __init__.py
│   └── generators.py
├── chaos_tests/            # Chaos engineering
│   ├── __init__.py
│   └── fault_injection.py
├── templates/              # Web UI templates
│   └── *.html
├── static/                 # Static assets
├── examples/               # Usage examples
├── tests/                  # Test suite
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── web_ui.py              # FastAPI application
├── cli.py                 # CLI interface
└── setup.py               # Package configuration
```

## Adding New Features

### Adding a New Workload

1. Create workload class in `benchmarking/workloads.py`:
```python
class CustomWorkload(Workload):
    def __init__(self):
        super().__init__(
            name="custom_workload",
            description="Description of workload",
            duration_seconds=30,
            weights={"read": 0.5, "write": 0.5}
        )
```

2. Register in `StandardWorkloads.get_all()`
3. Add tests in `tests/test_workloads.py`
4. Update documentation

### Adding a New Test Type

1. Create test class in appropriate module
2. Integrate with `TestRunnerService`
3. Add CLI command if needed
4. Add web UI integration
5. Write tests
6. Update documentation

### Adding MCP Server Support

1. Add server configuration in `mcp_client_expanded.py`
2. Test with basic operations
3. Add server-specific tests if needed
4. Update compatibility matrix in docs

## Testing Guidelines

### Unit Tests
* Test individual functions/methods
* Mock external dependencies
* Fast execution (<1 second per test)
* Located in `tests/unit/`

### Integration Tests
* Test component interactions
* Use real databases (SQLite)
* May use real MCP servers
* Located in `tests/integration/`

### End-to-End Tests
* Test complete workflows
* Use real services
* Located in `tests/e2e/`

## Documentation

### Docstring Format

Use Google style docstrings:

```python
def function(param1: str, param2: int = 0) -> bool:
    """
    Brief description of function.
    
    Longer description if needed, explaining behavior,
    edge cases, and important details.
    
    Args:
        param1: Description of param1
        param2: Description of param2, defaults to 0
    
    Returns:
        Description of return value
    
    Raises:
        ValueError: When param1 is empty
        TypeError: When param2 is not an integer
    
    Example:
        >>> function("test", 42)
        True
    """
```

### README Updates

When adding features, update the README:
* Add to feature list if significant
* Update usage examples
* Add to configuration section if needed

## Release Process

We use semantic versioning (MAJOR.MINOR.PATCH):

* MAJOR: Breaking changes
* MINOR: New features (backwards compatible)
* PATCH: Bug fixes

Releases are automated via GitHub Actions when tags are pushed:

```bash
git tag v1.2.3
git push origin v1.2.3
```

## Getting Help

* **Discord**: Join our community server
* **GitHub Issues**: For bugs and features
* **Email**: team@mcp-lab.com for security issues
* **Documentation**: https://docs.mcp-lab.com

## Recognition

Contributors will be:
* Listed in CONTRIBUTORS.md
* Mentioned in release notes
* Given credit in blog posts/announcements

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

Thank you for contributing to MCP Reliability Lab! 🎉