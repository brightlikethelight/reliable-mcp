# Changelog

All notable changes to MCP Reliability Lab will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Property-based testing improvements
- Additional chaos engineering scenarios
- Performance optimization for large-scale tests
- Support for custom MCP server configurations

## [1.0.0] - 2024-01-10

### Added
- Initial public release of MCP Reliability Lab
- Core MCP client implementation with stdio transport
- Scientific testing framework with four test types:
  - Property-based testing using Hypothesis
  - State machine testing for stateful operations
  - Chaos engineering with fault injection
  - Performance benchmarking with detailed metrics
- Seven standard workload patterns:
  - Real World Mix
  - CRUD Heavy
  - Read Intensive
  - Write Intensive  
  - Search Heavy
  - Concurrent Stress
  - Large Operations
- Web dashboard with real-time monitoring (FastAPI + HTMX)
- Command-line interface with full feature access
- Automatic leaderboard generation and scoring
- Server comparison capabilities
- Docker support with multi-stage builds
- PyPI package for easy installation
- One-command installer script
- Comprehensive documentation and examples
- SQLite-based metrics storage
- Retry logic with exponential backoff
- Consistency analysis with statistical metrics

### Fixed
- macOS path compatibility (/private/tmp usage)
- Consistency scoring algorithm improvements
- Module import path resolution
- SQLite schema compatibility

### Security
- No hardcoded credentials
- Secure default configurations
- Input validation on all endpoints

## [0.9.0] - 2024-01-05 (Beta)

### Added
- Beta release for early testing
- Basic MCP client functionality
- Initial web UI implementation
- Core benchmarking system
- Property testing framework

### Changed
- Switched from mock services to real implementations
- Replaced React with FastAPI + HTMX for simplicity

### Fixed
- Property test decorator conflicts
- Database initialization issues
- Import path problems

## [0.8.0] - 2024-01-01 (Alpha)

### Added
- Alpha release for internal testing
- Minimal MCP client with basic operations
- SQLite metrics storage
- Basic test runner service
- Initial benchmarking implementation

### Known Issues
- Consistency scoring returning 0%
- Mock services still in use
- Limited error handling

## [0.5.0] - 2023-12-20 (Pre-Alpha)

### Added
- Project initialization
- Basic project structure
- Initial MCP client prototype
- Concept validation

### Notes
- Not suitable for production use
- Many features incomplete
- For development only

## Version History Summary

| Version | Date       | Status      | Key Features                                    |
|---------|------------|-------------|------------------------------------------------|
| 1.0.0   | 2024-01-10 | Stable      | Full feature set, production ready            |
| 0.9.0   | 2024-01-05 | Beta        | Feature complete, testing phase               |
| 0.8.0   | 2024-01-01 | Alpha       | Core functionality working                    |
| 0.5.0   | 2023-12-20 | Pre-Alpha   | Initial prototype                             |

## Upgrade Guide

### From 0.9.0 to 1.0.0

1. Update installation:
```bash
pip install --upgrade mcp-reliability-lab
```

2. Database migration (if needed):
```bash
mcp-lab migrate-db
```

3. Configuration changes:
- Move from config.json to environment variables
- Update server definitions to new format

### From 0.8.0 to 0.9.0

1. Replace mock services with real implementations
2. Update import paths in custom code
3. Regenerate databases with new schema

## Deprecation Notice

### Deprecated in 1.0.0
- Mock service implementations (removed)
- Old configuration format (use new JSON schema)
- Legacy CLI commands (use new unified CLI)

### Planned Deprecations
- None currently planned

## Support

For upgrade assistance or questions:
- GitHub Issues: https://github.com/yourusername/mcp-reliability-lab/issues
- Documentation: https://docs.mcp-lab.com/upgrade
- Email: support@mcp-lab.com

---

[Unreleased]: https://github.com/yourusername/mcp-reliability-lab/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/yourusername/mcp-reliability-lab/releases/tag/v1.0.0
[0.9.0]: https://github.com/yourusername/mcp-reliability-lab/releases/tag/v0.9.0
[0.8.0]: https://github.com/yourusername/mcp-reliability-lab/releases/tag/v0.8.0
[0.5.0]: https://github.com/yourusername/mcp-reliability-lab/releases/tag/v0.5.0