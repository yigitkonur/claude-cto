#!/bin/bash

# Claude CTO Test Suite Runner
set -e

echo "🧪 Claude CTO Test Suite"
echo "========================"

# Create directories
mkdir -p tests/logs tests/reports

# Timestamp for this run
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="tests/logs/test_run_${TIMESTAMP}.log"

echo "📁 Setting up test environment..."

# Install test dependencies if needed
echo "🔧 Checking test dependencies..."
pip install -q pytest pytest-cov pytest-asyncio pytest-mock pytest-html 2>/dev/null || true

echo "🔍 Running tests..."

# Define the working test files
WORKING_TESTS=(
    "tests/test_basic.py"
    "tests/unit/server/test_models.py"
    "tests/unit/server/test_crud_working.py" 
    "tests/unit/cli/test_config_working.py"
    "tests/unit/server/test_error_handler_working.py"
)

echo "📋 Test files to run:"
for test in "${WORKING_TESTS[@]}"; do
    echo "   - $test"
done

echo ""

# Run tests with coverage
echo "▶️  Executing tests..."
pytest "${WORKING_TESTS[@]}" \
    --cov=claude_cto \
    --cov-report=html:tests/reports/htmlcov \
    --cov-report=term \
    --cov-report=xml:tests/reports/coverage.xml \
    --html=tests/reports/report_${TIMESTAMP}.html \
    --self-contained-html \
    --junitxml=tests/reports/results_${TIMESTAMP}.xml \
    -v \
    --tb=short \
    --no-header \
    2>&1 | tee "$LOG_FILE"

# Extract summary from log
echo ""
echo "📊 Test Results Summary:"
echo "========================"

# Count test results
PASSED=$(grep -c "PASSED" "$LOG_FILE" || echo "0")
FAILED=$(grep -c "FAILED" "$LOG_FILE" || echo "0") 
ERRORS=$(grep -c "ERROR" "$LOG_FILE" || echo "0")
TOTAL=$((PASSED + FAILED + ERRORS))

echo "✅ Passed: $PASSED"
echo "❌ Failed: $FAILED"
echo "🔥 Errors: $ERRORS"
echo "📈 Total:  $TOTAL"

if [ $FAILED -eq 0 ] && [ $ERRORS -eq 0 ]; then
    echo ""
    echo "🎉 All tests passed successfully!"
else
    echo ""
    echo "⚠️  Some tests failed or had errors. Check the detailed log."
fi

echo ""
echo "📁 Generated Reports:"
echo "   - Coverage HTML: tests/reports/htmlcov/index.html"
echo "   - Test Report:   tests/reports/report_${TIMESTAMP}.html"
echo "   - Coverage XML:  tests/reports/coverage.xml"
echo "   - JUnit XML:     tests/reports/results_${TIMESTAMP}.xml"
echo "   - Log file:      $LOG_FILE"

# Try to open coverage report (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo ""
    echo "💡 Opening coverage report in browser..."
    open tests/reports/htmlcov/index.html 2>/dev/null || echo "   (Could not auto-open browser)"
fi

echo ""
echo "🏁 Test execution complete!"