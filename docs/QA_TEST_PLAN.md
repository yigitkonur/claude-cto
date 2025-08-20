# Claude Worker - Comprehensive Manual QA Test Plan

## Test Plan Overview

**Version:** 0.3.1  
**Date:** 2025-08-20  
**Product:** Claude Worker - Fire-and-forget task execution system  
**Test Approach:** Manual Testing with Result Tracking

## Testable Features Inventory

### Core Features
1. **Installation Methods**
   - pip install with extras: [full], [server], [mcp]
   - Source installation via poetry
   - Smithery.ai deployment

2. **CLI Commands**
   - `claude-worker server` (start, health)
   - `claude-worker run` (with all options)
   - `claude-worker list`
   - `claude-worker status`

3. **Model Selection (NEW)**
   - CLI: --model parameter (sonnet/opus/haiku)
   - MCP: model parameter in create_task
   - API: model field in request body

4. **Input Methods**
   - Direct prompt argument
   - File path as prompt
   - Stdin piping
   - Watch mode (-w)

5. **REST API Endpoints**
   - GET /health
   - GET /api/v1/tasks
   - POST /api/v1/tasks
   - GET /api/v1/tasks/{id}
   - POST /api/v1/mcp/tasks (strict validation)

6. **MCP Server Modes**
   - Standalone (embedded database)
   - Proxy (connects to REST API)
   - Auto-detection based on server availability

7. **MCP Tools**
   - create_task (with validation rules)
   - get_task_status
   - list_tasks
   - get_task_logs (standalone only)
   - check_api_health (proxy only)

8. **Authentication**
   - Anthropic API Key
   - Claude Max/Pro OAuth
   - Fallback mechanism

9. **System Behaviors**
   - Auto-start server when not running
   - Port conflict resolution
   - Database persistence
   - Process isolation
   - Concurrent task execution
   - Crash recovery

10. **Configuration**
    - Environment variables
    - Default paths
    - Custom database location
    - Log directory configuration

## Test Environment Setup

### Prerequisites
- **OS:** Unix-like (Linux/macOS)
- **Python:** 3.10+
- **Node.js:** 16+ (for Claude Code SDK)
- **Tools:** curl, sqlite3, git, docker (optional)

### Authentication Setup
Choose one:
1. **API Key Method:**
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."
   ```

2. **OAuth Method:**
   ```bash
   claude login  # Follow prompts
   ```

### Test Workspace
```bash
mkdir -p ~/cw-test/project
cd ~/cw-test/project
echo "def main(): pass" > main.py
echo "def util(): pass" > utils.py
echo "Refactor main.py to add docstrings and type hints" > task.txt
```

### Pre-Test Cleanup
```bash
pkill -f claude-worker
rm -rf ~/.claude-worker
unset CLAUDE_WORKER_SERVER_URL
unset CLAUDE_WORKER_DB
```

---

## Test Cases

### Section 1: Installation Tests

| ID | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|----|-----------|-------|-----------------|-----------|-------|
| INS-01 | Full installation | `pip install "claude-worker[full]"` | Both `claude-worker` and `claude-worker-mcp` commands available | ⬜ | |
| INS-02 | Server-only installation | `pip install "claude-worker[server]"` | Only `claude-worker` available, no MCP | ⬜ | |
| INS-03 | MCP-only installation | `pip install "claude-worker[mcp]"` | Only `claude-worker-mcp` available | ⬜ | |
| INS-04 | Source installation | `git clone` → `poetry install` → `poetry shell` | All commands work in poetry shell | ⬜ | |
| INS-05 | Smithery installation | `npx @smithery/cli install @yigitkonur/claude-worker` | MCP server configured for Claude Desktop | ⬜ | |

### Section 2: Server Management Tests

| ID | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|----|-----------|-------|-----------------|-----------|-------|
| SRV-01 | Manual server start | `claude-worker server start` | Server starts on port 8000 | ⬜ | |
| SRV-02 | Auto port selection | Block 8000, then start server | Automatically uses port 8001 | ⬜ | |
| SRV-03 | Health check (running) | Start server → `claude-worker server health` | Shows "✓ Server is healthy" | ⬜ | |
| SRV-04 | Health check (stopped) | No server → `claude-worker server health` | Shows "✗ Server is not responding" | ⬜ | |
| SRV-05 | Auto-start on run | No server → `claude-worker run "test"` | Server auto-starts, task created | ⬜ | |

### Section 3: Task Creation Tests

| ID | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|----|-----------|-------|-----------------|-----------|-------|
| RUN-01 | Simple prompt | `claude-worker run "Add comments to main.py"` | Task created with ID | ⬜ | |
| RUN-02 | File as prompt | `claude-worker run task.txt` | Task uses file content | ⬜ | |
| RUN-03 | Stdin input | `echo "test" \| claude-worker run` | Task created from stdin | ⬜ | |
| RUN-04 | Watch mode | `claude-worker run "test" --watch` | Live updates shown | ⬜ | |
| RUN-05 | Custom directory | `claude-worker run "test" --dir /tmp` | Task runs in /tmp | ⬜ | |
| RUN-06 | Custom system prompt | `claude-worker run "test" -s "You are..."` | System prompt applied | ⬜ | |
| RUN-07 | No prompt error | `claude-worker run` | Error: "No prompt provided" | ⬜ | |

### Section 4: Model Selection Tests (NEW)

| ID | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|----|-----------|-------|-----------------|-----------|-------|
| MDL-01 | CLI sonnet model | `claude-worker run "test" --model sonnet` | Task uses sonnet (default) | ⬜ | |
| MDL-02 | CLI opus model | `claude-worker run "test" --model opus` | Task uses opus model | ⬜ | |
| MDL-03 | CLI haiku model | `claude-worker run "test" --model haiku` | Task uses haiku model | ⬜ | |
| MDL-04 | Invalid model error | `claude-worker run "test" --model gpt4` | Error: "Invalid model" | ⬜ | |
| MDL-05 | API model field | POST with `{"model": "opus"}` | Task created with opus | ⬜ | |
| MDL-06 | MCP model parameter | `create_task(..., model="haiku")` | Task uses haiku | ⬜ | |
| MDL-07 | Model in database | Create task → check DB | Model field stored correctly | ⬜ | |
| MDL-08 | Model in logs | Create task → check logs | Logs show: "Model: opus" | ⬜ | |

### Section 5: Task Management Tests

| ID | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|----|-----------|-------|-----------------|-----------|-------|
| LST-01 | List empty tasks | Fresh DB → `claude-worker list` | "No tasks found yet!" | ⬜ | |
| LST-02 | List multiple tasks | Create 3 tasks → `list` | Table shows all 3 tasks | ⬜ | |
| LST-03 | Status valid ID | `claude-worker status 1` | Detailed info for task 1 | ⬜ | |
| LST-04 | Status invalid ID | `claude-worker status 999` | "Task ID 999 not found" | ⬜ | |
| LST-05 | Status no ID | Multiple tasks → `status` | Shows available task IDs | ⬜ | |

### Section 6: REST API Tests

| ID | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|----|-----------|-------|-----------------|-----------|-------|
| API-01 | Health endpoint | `curl http://localhost:8000/health` | 200 OK, {"status":"healthy"} | ⬜ | |
| API-02 | Create task | POST to `/api/v1/tasks` | 200 OK, returns task ID | ⬜ | |
| API-03 | List all tasks | GET `/api/v1/tasks` | 200 OK, JSON array | ⬜ | |
| API-04 | Get specific task | GET `/api/v1/tasks/1` | 200 OK, task details | ⬜ | |
| API-05 | Task not found | GET `/api/v1/tasks/999` | 404 Not Found | ⬜ | |
| API-06 | Model in API | POST with model field | Task created with model | ⬜ | |

### Section 7: MCP Validation Tests

| ID | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|----|-----------|-------|-----------------|-----------|-------|
| MCP-01 | Prompt too short | create_task("fix") | Error: "min 150 chars" | ⬜ | |
| MCP-02 | No path in prompt | create_task("long text no path...") | Error: "must contain path" | ⬜ | |
| MCP-03 | Missing John Carmack | system_prompt without "John Carmack" | Error: "must contain John Carmack" | ⬜ | |
| MCP-04 | System prompt length | < 75 or > 500 chars | Error: "75-500 characters" | ⬜ | |
| MCP-05 | Valid MCP request | All validations pass | Task created successfully | ⬜ | |
| MCP-06 | Invalid model in MCP | model="invalid" | Error: "Invalid model" | ⬜ | |

### Section 8: MCP Mode Detection

| ID | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|----|-----------|-------|-----------------|-----------|-------|
| MOD-01 | Standalone mode | No server → run MCP | Uses embedded database | ⬜ | |
| MOD-02 | Proxy mode | Server running → run MCP | Connects to REST API | ⬜ | |
| MOD-03 | Mode switch | Start server while MCP running | Next request uses proxy | ⬜ | |
| MOD-04 | check_api_health | In proxy mode | Returns API health | ⬜ | |
| MOD-05 | get_task_logs | In standalone mode | Returns local logs | ⬜ | |

### Section 9: Authentication Tests

| ID | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|----|-----------|-------|-----------------|-----------|-------|
| AUTH-01 | API key auth | Set ANTHROPIC_API_KEY → run task | Task executes | ⬜ | |
| AUTH-02 | OAuth auth | claude login → unset API_KEY → run | Task executes | ⬜ | |
| AUTH-03 | Auth fallback | Invalid API_KEY → OAuth valid | Falls back to OAuth | ⬜ | |
| AUTH-04 | No auth | No API_KEY, no OAuth → run | Task fails with auth error | ⬜ | |
| AUTH-05 | Auth in logs | Check task logs | Shows auth method used | ⬜ | |

### Section 10: System Behavior Tests

| ID | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|----|-----------|-------|-----------------|-----------|-------|
| SYS-01 | Database persistence | Create task → restart server → check | Task still exists | ⬜ | |
| SYS-02 | Crash recovery | Kill server during task → restart | Task status preserved | ⬜ | |
| SYS-03 | Concurrent tasks | Submit 3 tasks rapidly | All created, no locks | ⬜ | |
| SYS-04 | Worker limit | Submit 5 tasks | Max 4 run simultaneously | ⬜ | |
| SYS-05 | Custom DB path | Set CLAUDE_WORKER_DB=/tmp/test.db | Uses custom location | ⬜ | |
| SYS-06 | Log rotation | Run many tasks | Logs organized by date | ⬜ | |

### Section 11: Docker & Deployment Tests

| ID | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|----|-----------|-------|-----------------|-----------|-------|
| DKR-01 | Docker build | `docker build -t cw-test .` | Build succeeds | ⬜ | |
| DKR-02 | Docker run | `docker run cw-test` | Container starts | ⬜ | |
| DKR-03 | Docker health | Container running → curl health | 200 OK | ⬜ | |
| DKR-04 | Docker volume | Mount /data → create task | Data persists | ⬜ | |
| DKR-05 | Smithery build | Check Dockerfile + smithery.yaml | Valid configuration | ⬜ | |

### Section 12: Documentation Tests

| ID | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|----|-----------|-------|-----------------|-----------|-------|
| DOC-01 | README commands | Copy/paste each command | All execute correctly | ⬜ | |
| DOC-02 | Link validity | Click all docs/*.md links | All files exist | ⬜ | |
| DOC-03 | Example accuracy | Run all code examples | Work as documented | ⬜ | |
| DOC-04 | Troubleshooting | Follow debug steps | Produce useful output | ⬜ | |
| DOC-05 | Changelog | Check version consistency | Matches pyproject.toml | ⬜ | |

---

## Test Execution Instructions

### 1. Environment Preparation
1. Clone repository to test machine
2. Set up Python virtual environment
3. Configure authentication (API key or OAuth)
4. Create test workspace

### 2. Test Execution Order
1. Installation tests (Section 1)
2. Server tests (Section 2)
3. Core functionality (Sections 3-5)
4. API and MCP (Sections 6-8)
5. System behaviors (Sections 9-10)
6. Deployment (Section 11)
7. Documentation (Section 12)

### 3. Result Recording
- ✅ Pass: Feature works as expected
- ❌ Fail: Feature does not work or has bugs
- ⚠️ Partial: Works with issues
- ⬜ Not tested: Pending execution

### 4. Issue Reporting
For each failure:
1. Note the test case ID
2. Capture error messages/screenshots
3. Document reproduction steps
4. File GitHub issue with label "qa-testing"

---

## Test Summary

**Total Test Cases:** 67  
**Critical Tests:** Model selection, Authentication, MCP validation  
**Test Coverage:** All documented features + edge cases

### Sign-off Criteria
- All critical tests pass
- No more than 5% non-critical failures
- All failures have documented workarounds
- Documentation tests 100% pass

---

**QA Tester:** _________________  
**Date Executed:** _________________  
**Version Tested:** 0.3.1  
**Overall Result:** ⬜ Pass / ⬜ Fail