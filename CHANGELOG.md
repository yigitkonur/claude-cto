# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2025-01-11

### Added
- Enhanced server start command with comprehensive user guidance panel
- Automatic port detection when default port 8000 is occupied
- Rich formatted output showing WHY, HOW, and WHEN to use Claude Worker
- Dynamic port warnings and environment variable suggestions
- Improved visual hierarchy with emojis and color coding

### Improved
- Server startup experience with informative onboarding messages
- Error handling with helpful tips when ports are unavailable
- CLI help display when no command is provided

## [0.1.1] - 2025-01-11

### Fixed
- PyPI publishing workflow using API token authentication

## [0.1.0] - 2025-01-11

### Added
- Initial release of claude-worker
- Fire-and-forget task execution system for Claude Code SDK
- CLI interface for task management
- REST API for programmatic access
- MCP-compatible endpoints with strict validation
- Process isolation via ProcessPoolExecutor
- SQLite database for task persistence
- Real-time task monitoring with --watch flag
- Support for custom system prompts with John Carmack principles
- Comprehensive documentation and usage guide
- Multiple installation modes (MCP-only, Server+CLI, Full)
- Automatic log file management and rotation
- Task status tracking (pending, running, completed, failed)
- Detailed error reporting and logging