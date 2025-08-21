"""
Examples of using the enhanced MCP create_task with dependencies and delays.
Shows various patterns for creating dependent workflows.
"""

# ============================================================================
# EXAMPLE 1: Simple Sequential Workflow
# ============================================================================

# User says: "Analyze my code and fix any issues found"

# Claude would create tasks with dependencies:

# Step 1: Analyze the code
await create_task(
    task_identifier="analyze_code",
    execution_prompt="Analyze all Python files in /Users/john/project for code quality issues, complexity, and potential bugs. Create a detailed report.",
    working_directory="/Users/john/project",
    model="sonnet"
)

# Step 2: Fix issues (depends on analysis)
await create_task(
    task_identifier="fix_issues",
    execution_prompt="Fix all code quality issues identified in the analysis report for /Users/john/project. Preserve functionality while improving code quality.",
    working_directory="/Users/john/project",
    depends_on=["analyze_code"],  # Wait for analysis to complete
    model="opus"  # Use more powerful model for fixes
)

# Step 3: Run tests (depends on fixes)
await create_task(
    task_identifier="run_tests",
    execution_prompt="Run the complete test suite in /Users/john/project and ensure all tests pass after the fixes.",
    working_directory="/Users/john/project",
    depends_on=["fix_issues"],  # Wait for fixes to complete
    wait_after_dependencies=2.0,  # Wait 2 seconds for file system to sync
    model="haiku"  # Simple task, use fast model
)

# ============================================================================
# EXAMPLE 2: Parallel Work with Final Aggregation
# ============================================================================

# User says: "Analyze my entire codebase across different languages"

# Claude creates parallel analysis tasks that merge at the end:

# Parallel Task 1: Python analysis
await create_task(
    task_identifier="analyze_python",
    execution_prompt="Analyze all Python files in /Users/john/project for patterns, complexity, and create a Python-specific report in reports/python.md",
    working_directory="/Users/john/project",
    orchestration_group="codebase_analysis",
    model="sonnet"
)

# Parallel Task 2: JavaScript analysis
await create_task(
    task_identifier="analyze_javascript", 
    execution_prompt="Analyze all JavaScript and TypeScript files in /Users/john/project and create a JS-specific report in reports/javascript.md",
    working_directory="/Users/john/project",
    orchestration_group="codebase_analysis",
    model="sonnet"
)

# Parallel Task 3: SQL analysis
await create_task(
    task_identifier="analyze_sql",
    execution_prompt="Analyze all SQL files and database schemas in /Users/john/project and create a database report in reports/sql.md",
    working_directory="/Users/john/project",
    orchestration_group="codebase_analysis",
    model="sonnet"
)

# Final Task: Combine all reports (waits for all analyses)
await create_task(
    task_identifier="combine_reports",
    execution_prompt="Read all analysis reports from reports/ directory in /Users/john/project and create a comprehensive executive summary in ANALYSIS_SUMMARY.md",
    working_directory="/Users/john/project",
    depends_on=["analyze_python", "analyze_javascript", "analyze_sql"],  # Wait for ALL
    wait_after_dependencies=3.0,  # Give time for all files to be written
    orchestration_group="codebase_analysis",
    model="opus"  # Use powerful model for synthesis
)

# ============================================================================
# EXAMPLE 3: Complex Multi-Stage Pipeline
# ============================================================================

# User says: "Modernize my legacy codebase"

# Claude creates a sophisticated pipeline:

# Stage 1: Backup
await create_task(
    task_identifier="backup",
    execution_prompt="Create a complete backup of all code in /Users/john/legacy-app to backup/timestamp/ directory with current timestamp",
    working_directory="/Users/john/legacy-app",
    orchestration_group="modernization",
    model="haiku"
)

# Stage 2a: Analyze dependencies (after backup)
await create_task(
    task_identifier="analyze_deps",
    execution_prompt="Analyze package.json, requirements.txt, and other dependency files in /Users/john/legacy-app. Identify outdated and vulnerable dependencies.",
    working_directory="/Users/john/legacy-app",
    depends_on=["backup"],
    orchestration_group="modernization",
    model="sonnet"
)

# Stage 2b: Analyze code patterns (after backup, parallel with deps)
await create_task(
    task_identifier="analyze_patterns",
    execution_prompt="Analyze code patterns in /Users/john/legacy-app. Identify deprecated APIs, anti-patterns, and modernization opportunities.",
    working_directory="/Users/john/legacy-app",
    depends_on=["backup"],
    orchestration_group="modernization",
    model="sonnet"
)

# Stage 3: Update dependencies (after analysis)
await create_task(
    task_identifier="update_deps",
    execution_prompt="Update all dependencies in /Users/john/legacy-app to latest stable versions. Fix any breaking changes.",
    working_directory="/Users/john/legacy-app",
    depends_on=["analyze_deps"],
    wait_after_dependencies=1.0,
    orchestration_group="modernization",
    model="opus"
)

# Stage 4: Modernize code (after patterns analysis and deps update)
await create_task(
    task_identifier="modernize_code",
    execution_prompt="Modernize code patterns in /Users/john/legacy-app. Update to modern syntax, async/await, type hints, etc.",
    working_directory="/Users/john/legacy-app",
    depends_on=["analyze_patterns", "update_deps"],  # Wait for BOTH
    wait_after_dependencies=2.0,
    orchestration_group="modernization",
    model="opus"
)

# Stage 5: Add tests (after modernization)
await create_task(
    task_identifier="add_tests",
    execution_prompt="Add comprehensive test coverage for all modernized code in /Users/john/legacy-app. Ensure 80% coverage minimum.",
    working_directory="/Users/john/legacy-app",
    depends_on=["modernize_code"],
    orchestration_group="modernization",
    model="sonnet"
)

# Stage 6: Final validation (after everything)
await create_task(
    task_identifier="validate",
    execution_prompt="Run full test suite, linters, and type checkers in /Users/john/legacy-app. Create a final modernization report.",
    working_directory="/Users/john/legacy-app",
    depends_on=["add_tests"],
    wait_after_dependencies=3.0,  # Give time for all changes to settle
    orchestration_group="modernization",
    model="haiku"
)

# ============================================================================
# EXAMPLE 4: Conditional Dependencies with Wait Times
# ============================================================================

# User says: "Deploy my application with proper checks"

# Claude creates deployment pipeline with safety checks:

# Build the application
await create_task(
    task_identifier="build_app",
    execution_prompt="Run the build process for the application in /Users/john/app. Create production build in dist/ directory.",
    working_directory="/Users/john/app",
    model="haiku"
)

# Run unit tests
await create_task(
    task_identifier="unit_tests",
    execution_prompt="Run all unit tests in /Users/john/app and ensure 100% pass rate.",
    working_directory="/Users/john/app",
    depends_on=["build_app"],
    model="haiku"
)

# Run integration tests (with delay for services to start)
await create_task(
    task_identifier="integration_tests",
    execution_prompt="Start test services and run integration tests in /Users/john/app.",
    working_directory="/Users/john/app",
    depends_on=["unit_tests"],
    wait_after_dependencies=5.0,  # Wait 5 seconds for services to be ready
    model="sonnet"
)

# Deploy to staging
await create_task(
    task_identifier="deploy_staging",
    execution_prompt="Deploy the built application from /Users/john/app/dist to staging environment.",
    working_directory="/Users/john/app",
    depends_on=["integration_tests"],
    wait_after_dependencies=2.0,
    model="haiku"
)

# Smoke tests on staging (with delay for deployment)
await create_task(
    task_identifier="smoke_tests",
    execution_prompt="Run smoke tests against the staging deployment of /Users/john/app. Verify all critical paths work.",
    working_directory="/Users/john/app",
    depends_on=["deploy_staging"],
    wait_after_dependencies=10.0,  # Wait 10 seconds for deployment to stabilize
    model="sonnet"
)

# Deploy to production (only if all tests pass)
await create_task(
    task_identifier="deploy_production",
    execution_prompt="Deploy the validated application from /Users/john/app/dist to production environment.",
    working_directory="/Users/john/app",
    depends_on=["smoke_tests"],
    wait_after_dependencies=5.0,  # Final safety delay
    model="haiku"
)

# ============================================================================
# KEY PATTERNS AND BEST PRACTICES
# ============================================================================

"""
1. IDENTIFIER NAMING:
   - Use descriptive, action-based names: "analyze_code", "fix_bugs", "run_tests"
   - Use underscores for readability
   - Keep them unique within your workflow

2. DEPENDENCY PATTERNS:
   - Sequential: A → B → C (each depends on previous)
   - Parallel with merge: A, B, C → D (D depends on all three)
   - Diamond: A → B, C → D (B and C both depend on A, D depends on both)

3. WAIT TIMES:
   - File system sync: 1-2 seconds
   - Service startup: 5-10 seconds
   - API propagation: 2-5 seconds
   - Deployment stabilization: 10-30 seconds

4. MODEL SELECTION WITH DEPENDENCIES:
   - Analysis tasks: "sonnet" (balanced)
   - Complex refactoring: "opus" (powerful)
   - Simple checks/validations: "haiku" (fast)
   - Tasks that depend on many others: Consider using "opus" for synthesis

5. ORCHESTRATION GROUPS:
   - Use when tasks are logically related
   - Helps with tracking and management
   - Can submit all at once with submit_orchestration()

6. ERROR HANDLING:
   - If a dependency fails, dependent tasks are automatically skipped
   - Use this to create "fail-fast" workflows
   - Critical tasks should be early in the dependency chain
"""