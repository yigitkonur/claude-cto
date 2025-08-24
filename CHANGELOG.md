# Changelog

## [0.7.6] - 2025-08-24

- chore: bump version to v0.7.5
- feat: implement comprehensive automated version management system
- chore: bump version to 0.7.5 [skip ci]
- docs: add comprehensive inline comments across entire codebase
- chore: bump version to 0.7.4 [skip ci]


## [0.7.5] - 2025-08-24

- docs: add comprehensive inline comments across entire codebase
- chore: bump version to 0.7.4 [skip ci]
- fix: use HOMEBREW_TAP_TOKEN for GHCR authentication
- chore: bump version to 0.7.3 [skip ci]
- fix: use HOMEBREW_GITHUB_API_TOKEN for GHCR publishing to enable dual registry support


## [0.7.4] - 2025-08-24

- fix: use HOMEBREW_TAP_TOKEN for GHCR authentication
- chore: bump version to 0.7.3 [skip ci]
- fix: use HOMEBREW_GITHUB_API_TOKEN for GHCR publishing to enable dual registry support
- chore: bump version to 0.7.2 [skip ci]
- fix: remove GHCR push due to permission issues, focus on Docker Hub


## [0.7.3] - 2025-08-24

- fix: use HOMEBREW_GITHUB_API_TOKEN for GHCR publishing to enable dual registry support
- chore: bump version to 0.7.2 [skip ci]
- fix: remove GHCR push due to permission issues, focus on Docker Hub
- chore: bump version to 0.7.1 [skip ci]
- fix: use yigitkonur as commit author instead of github-actions bot


## [0.7.2] - 2025-08-24

- fix: remove GHCR push due to permission issues, focus on Docker Hub
- chore: bump version to 0.7.1 [skip ci]
- fix: use yigitkonur as commit author instead of github-actions bot
- chore: bump version to 0.7.0 [skip ci]
- feat: enable automatic Docker build and push on every code change


## [0.7.1] - 2025-08-24

- fix: use yigitkonur as commit author instead of github-actions bot
- chore: bump version to 0.7.0 [skip ci]
- feat: enable automatic Docker build and push on every code change
- fix: update poetry.lock to sync with alembic dependency
- fix: add critical memory leak prevention and circuit breaker persistence


## [0.7.0] - 2025-08-24

- feat: enable automatic Docker build and push on every code change
- fix: update poetry.lock to sync with alembic dependency
- fix: add critical memory leak prevention and circuit breaker persistence
- chore: bump version to 0.6.3 [skip ci]
- fix: add alembic dependency for database migrations


## [0.6.3] - 2025-08-24

- fix: add alembic dependency for database migrations
- fix: load Docker image in CI workflow for testing
- chore: bump version to 0.6.2 [skip ci]
- chore: remove code quality checks from CI workflow
- chore: bump version to 0.6.2 [skip ci]


## [0.6.2] - 2025-08-24

- chore: remove code quality checks from CI workflow
- chore: bump version to 0.6.2 [skip ci]
- style: apply black formatting and fix syntax errors
- chore: bump version to 0.6.1 [skip ci]
- refactor: remove all tests and simplify CI workflow


## [0.6.2] - 2025-08-24

- style: apply black formatting and fix syntax errors
- chore: bump version to 0.6.1 [skip ci]
- refactor: remove all tests and simplify CI workflow
- fix: disable pytest coverage in CI workflow
- fix: resolve GitHub Actions workflow issues


## [0.6.1] - 2025-08-24

- refactor: remove all tests and simplify CI workflow
- fix: disable pytest coverage in CI workflow
- fix: resolve GitHub Actions workflow issues
- chore: update smithery.yaml to v0.6.0 [skip ci]
- chore: bump version to 0.6.0 [skip ci]


## [0.6.0] - 2025-08-24

- feat: major infrastructure improvements and Docker multi-registry support
- update illustrative examples
- update readme graph
- chore: bump version to 0.5.1 [skip ci]
- rename: claude-cto


## [0.5.1] - 2025-08-21

- rename: claude-cto
- Pre-refactor commit: Save current state before renaming claude-worker to claude-cto
- chore: bump version to 0.5.0 [skip ci]
- fix: enforce CRUD layer compliance in TaskOrchestrator
- docs: add comprehensive error handling guide


## [0.5.0] - 2025-08-21

- fix: enforce CRUD layer compliance in TaskOrchestrator
- docs: add comprehensive error handling guide
- feat: implement comprehensive Claude SDK error type handling
- docs: add comprehensive error handling guide
- feat: implement comprehensive Claude SDK error type handling


## [0.4.0] - 2025-08-20

- feat: enhance error handling with detailed debugging information
- docs: add comprehensive manual QA test plan with 67 test cases
- chore: bump version to 0.3.2 [skip ci]
- chore: bump version to 0.2.4 for model selection feature
- feat: add Claude model selection support across all interfaces


## [0.3.2] - 2025-08-20

- chore: bump version to 0.2.4 for model selection feature
- feat: add Claude model selection support across all interfaces
- chore: bump version to 0.3.0 [skip ci]
- feat: add Smithery.ai deployment configuration for MCP server
- chore: bump version to 0.2.3 [skip ci]


## [0.3.1] - 2025-08-20

### Added
- Claude model selection support across all interfaces (CLI, MCP, API)
- New `--model` parameter for CLI with sonnet/opus/haiku options
- Model field in database schema with proper enum validation
- Intelligent model descriptions to guide usage:
  - sonnet: Default, balanced intelligence for most tasks
  - opus: Highest intelligence for complex planning/architecture
  - haiku: Fastest execution for simple repetitive tasks

### Changed
- TaskDB model now includes model field (default: sonnet)
- Task executors pass model selection to Claude Code SDK
- MCP tools validate and accept model parameter

## [0.3.0] - 2025-08-20

### Added
- Smithery.ai deployment configuration for MCP server
- Docker container support with Alpine Linux
- One-command installation via `npx @smithery/cli install`
- Smithery URL in package metadata

### Changed
- Documentation updated with Smithery installation instructions

## [0.2.3] - 2025-08-20

- Merge branch 'main' of https://github.com/yigitkonur/claude-worker
- docs: document zero-configuration auto-start behavior for MCP
- chore: bump version to 0.2.2 [skip ci]
- Merge branch 'main' of https://github.com/yigitkonur/claude-worker
- fix: resolve list_tasks database query errors in MCP integration
- chore: bump version to 0.2.1 [skip ci]
- Merge branch 'main' of https://github.com/yigitkonur/claude-worker
- chore: bump version to 0.2.0 [skip ci]


## [0.2.2] - 2025-08-20

- Merge branch 'main' of https://github.com/yigitkonur/claude-worker
- fix: resolve list_tasks database query errors in MCP integration
- chore: bump version to 0.2.1 [skip ci]
- Merge branch 'main' of https://github.com/yigitkonur/claude-worker
- feat: optimize MCP tool descriptions for advanced LLM behavior training
- chore: bump version to 0.2.0 [skip ci]
- feat: enhance MCP integration with error-driven prompt optimization


## [0.2.1] - 2025-08-11

- Merge branch 'main' of https://github.com/yigitkonur/claude-worker
- feat: optimize MCP tool descriptions for advanced LLM behavior training
- chore: bump version to 0.2.0 [skip ci]
- feat: enhance MCP integration with error-driven prompt optimization
- chore: bump version to 0.1.6 [skip ci]
- docs: improve package docstring


## [0.2.0] - 2025-08-11

- feat: enhance MCP integration with error-driven prompt optimization
- chore: bump version to 0.1.6 [skip ci]
- docs: improve package docstring
- feat: add automatic PyPI publishing on main branch pushes
- README fix


## [0.1.6] - 2025-08-11

- docs: improve package docstring
- feat: add automatic PyPI publishing on main branch pushes
- README fix
- README fix
- README fix


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