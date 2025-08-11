# Advanced Task Submission Methods

The `claude-worker run` command offers multiple ways to submit tasks, making it powerful for both interactive use and automated workflows. This guide covers all submission methods with practical examples.

> **🔍 Behind the Scenes:** The CLI automatically detects input sources (arguments, files, or stdin) using smart detection logic in `cli/main.py`.

## 1. Command-Line Arguments

**Best for:** Quick, interactive tasks and simple automation.

### Simple Prompts

```bash
claude-worker run "Create a README.md for my project, highlighting its key features."
```

### Multi-line Prompts

Use quotes for complex, structured prompts:

```bash
claude-worker run "Create a comprehensive Python web scraper that:
1. Accepts a list of URLs
2. Extracts all text content from each page  
3. Saves the results to a single CSV file
4. Includes robust error handling for network issues
5. Logs its progress to the console"
```

### With Additional Options

Combine with other flags for better control:

```bash
claude-worker run "Refactor this authentication module" \
  --dir ./src/auth \
  --system "You are a security-focused Python developer. Follow Django best practices." \
  --watch
```

## 2. File-Based Prompts

**Best for:** Reusable templates, complex instructions, and team collaboration.

### Creating Prompt Templates

**`prompts/code-review.txt`:**
```
Analyze the provided codebase and generate a comprehensive technical review including:

- Code quality assessment (readability, maintainability, performance)
- Security vulnerability scan
- Architecture recommendations  
- Test coverage suggestions
- Documentation improvements needed

Format the output as a structured Markdown report with actionable items.
```

**`prompts/api-docs.txt`:**
```
Generate complete API documentation in OpenAPI 3.0 format for this codebase:

1. Analyze all endpoints and data models
2. Include request/response schemas
3. Add comprehensive examples for each endpoint
4. Document authentication requirements
5. Generate a Postman collection file

Save as api-documentation.yml and api-examples.postman_collection.json
```

### Using File Prompts

```bash
# Basic usage
claude-worker run prompts/code-review.txt --dir ./src

# With custom system prompt
claude-worker run prompts/api-docs.txt \
  --dir ./backend \
  --system "You are a technical writer specializing in API documentation" \
  --watch
```

### 🔄 Template Management

Create a `prompts/` directory for reusable templates:

```bash
mkdir prompts
echo "Your reusable prompt here" > prompts/template-name.txt
claude-worker run prompts/template-name.txt --dir ./project
```

## 3. Standard Input (stdin) 

**Best for:** Shell scripting, automation, and dynamic content processing.

### Dynamic Prompts with `echo`

```bash
# Simple dynamic prompts
TASK="Analyze the log file for security issues"
echo "$TASK" | claude-worker run --dir /var/logs

# Date-aware prompts
echo "Generate a daily standup report for $(date +%Y-%m-%d)" | claude-worker run
```

### Content Processing with `cat`

```bash
# Analyze existing code
cat src/main.py | claude-worker run "Refactor this Python code for better performance"

# Process configuration files
cat config.json | claude-worker run "Validate this JSON config and suggest improvements"
```

### Advanced Unix Pipeline Integration

**Directory Analysis:**
```bash
# Get project structure overview
find . -type f -name "*.py" | head -10 | claude-worker run "Analyze this Python project structure"

# Process git logs
git log --oneline -10 | claude-worker run "Summarize recent development activity"
```

**Log Processing:**
```bash
# Analyze error logs
tail -100 /var/log/app.log | grep ERROR | claude-worker run "Analyze these error patterns"

# Process server metrics
ps aux | head -20 | claude-worker run "Analyze current system resource usage"
```

**Batch Processing:**
```bash
# Process multiple files (creates separate tasks)
find . -name "*.py" | xargs -I {} claude-worker run "Review the code in {}"

# Process with custom working directory for each
find ./modules -name "*.py" | xargs -I {} claude-worker run "Document this module" --dir $(dirname {})
```

### 🚀 Automation Scripts

**Example: Daily Code Analysis Script**
```bash
#!/bin/bash
# daily-analysis.sh

# Get recent changes
RECENT_FILES=$(git diff --name-only HEAD~1 HEAD | grep -E '\.(py|js|ts)$')

if [ -n "$RECENT_FILES" ]; then
    echo "Analyze these recently changed files for potential issues:" > /tmp/analysis-prompt.txt
    echo "$RECENT_FILES" >> /tmp/analysis-prompt.txt
    
    claude-worker run /tmp/analysis-prompt.txt \
      --system "You are a senior code reviewer focused on catching bugs and security issues" \
      --watch
fi
```

### ⚠️ Important Notes

- **Multiple Tasks**: Using `xargs` creates separate tasks for each input
- **Large Content**: stdin content is included in the prompt, so be mindful of size limits
- **Shell Escaping**: Be careful with special characters in piped content

---

## Comparison & Best Practices

| Method | Best For | Pros | Cons |
|--------|----------|------|------|
| **Command Args** | Quick tasks, interactive use | Simple, fast | Limited reusability |
| **File Prompts** | Complex tasks, team collaboration | Reusable, version controlled | Extra file management |
| **stdin Pipes** | Automation, dynamic content | Very flexible, scriptable | Complex setup |

### 💡 Pro Tips

**1. Combine Methods:**
```bash
# Use file template with dynamic content
cat recent-changes.txt | claude-worker run prompts/review-template.txt
```

**2. Environment-Specific Prompts:**
```bash
# Development vs production analysis
claude-worker run prompts/deploy-checklist.txt --dir ./dist --system "Environment: production"
```

**3. Task Chaining:**
```bash
# Run dependent tasks
claude-worker run "Generate unit tests for new features" --watch
# Then run the tests after completion
```

**4. Debugging Submission Issues:**
```bash
# Check what content would be sent
echo "test prompt" | claude-worker run --help  # Shows the prompt detection
```

## Next Steps

- 📊 **[Monitoring & Logs](./02-user-guide-monitoring-and-logs.md)**: Track your submitted tasks
- ⚙️ **[CLI Reference](./02-user-guide-cli-reference.md)**: Complete command options
- 🔧 **[Configuration Guide](./05-administration-configuration.md)**: Customize behavior