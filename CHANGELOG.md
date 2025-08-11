# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.5] - 2025-08-11

### 🎯 Major User Experience Improvements

- **✅ Auto-start server** — No manual server management needed! Claude Worker automatically starts the server when you run tasks
- **✅ Rich help text** — Clear examples and guidance everywhere with beautiful formatting
- **✅ Smart defaults** — Commands work intuitively without flags (`claude-worker status` shows available tasks)
- **✅ Helpful errors** — Guide users instead of confusing them with actionable solutions
- **✅ No missing arguments** — Status command shows available IDs when none provided
- **✅ Visual feedback** — Colors, emojis, and clear formatting throughout the CLI

### 🔐 Dual Authentication Support

- **Claude Max/Pro Subscription (OAuth)** — Now works with your Claude subscription without requiring an API key!
- **Smart Authentication Priority** — Automatically tries API key first, then falls back to Claude CLI OAuth
- **Zero Configuration** — No setup needed, works with whatever authentication you have available
- **Updated Documentation** — Comprehensive guides for both authentication methods

### Added
- Auto-start server functionality for all CLI commands
- Rich help text with examples and emojis throughout CLI
- Smart defaults for commands (status without ID shows available tasks)
- Comprehensive authentication troubleshooting guide
- OAuth authentication support via Claude CLI
- Beginner-friendly error messages with actionable solutions
- Visual improvements with colors and formatting

### Fixed
- Claude Worker now works with Claude Max/Pro subscriptions (OAuth)
- Server starts automatically when needed (no manual intervention)
- Status command is beginner-friendly (shows available tasks when no ID provided)
- Authentication priority handling (API key → OAuth fallback)
- ProcessPoolExecutor issues with OAuth authentication
- Task execution with automated permission handling

### Improved
- Complete CLI user experience overhaul
- Documentation updated for dual authentication methods
- Error messages are now helpful and actionable
- All commands provide guidance and examples
- Server management is now invisible to users

## [0.1.4] - 2025-01-11

### Fixed
- Fixed database schema mismatches between models and CRUD operations
- Fixed incorrect field names (`raw_log_path`/`summary_log_path` → `log_file_path`)
- Fixed enum usage for task status (now uses proper `TaskStatus` enum)
- Fixed TypeError in `list` command when `last_action_cache` is None
- Fixed 501 HTTP error when submitting tasks to the server

### Improved
- Consistent use of TaskStatus enum throughout the codebase
- Better null handling in CLI display functions

## [0.1.3] - 2025-01-11

### Added
- Automatic port detection with `--auto-port` flag (enabled by default)
- Improved CLI help display - shows help message when no command is provided
- Better error messages when port conflicts occur

### Fixed
- Fixed module import path from `src.server.main` to `claude_worker.server.main`
- CLI now properly handles port conflicts by trying alternative ports (8001-8009)

### Improved
- User-friendly CLI behavior for novice users
- Clear guidance when server runs on non-default port
- Environment variable hints for connecting to non-default ports

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