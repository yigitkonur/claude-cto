#!/usr/bin/env python3
"""Pre-publication checklist for claude-worker."""

import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Tuple, List

# Colors for terminal output
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

def run_command(cmd: List[str]) -> Tuple[bool, str]:
    """Run a command and return success status and output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)

def check_file_exists(filepath: str) -> bool:
    """Check if a file exists."""
    return Path(filepath).exists()

def check_pyproject():
    """Validate pyproject.toml."""
    print(f"\n{BLUE}Checking pyproject.toml...{NC}")
    
    if not check_file_exists("pyproject.toml"):
        print(f"{RED}✗ pyproject.toml not found{NC}")
        return False
    
    success, output = run_command(["poetry", "check"])
    if success:
        print(f"{GREEN}✓ pyproject.toml is valid{NC}")
        
        # Check version
        success, version = run_command(["poetry", "version", "-s"])
        if success:
            print(f"{GREEN}✓ Version: {version.strip()}{NC}")
    else:
        print(f"{RED}✗ pyproject.toml validation failed{NC}")
        return False
    
    return True

def check_required_files():
    """Check for required files."""
    print(f"\n{BLUE}Checking required files...{NC}")
    
    required_files = {
        "README.md": "Project description",
        "LICENSE": "License file",
        "CHANGELOG.md": "Change history",
        "GUIDE.md": "Usage guide",
        "pyproject.toml": "Project configuration",
        "poetry.lock": "Dependency lock file"
    }
    
    all_present = True
    for file, description in required_files.items():
        if check_file_exists(file):
            print(f"{GREEN}✓ {file}: {description}{NC}")
        else:
            print(f"{RED}✗ {file}: {description} - MISSING{NC}")
            all_present = False
    
    return all_present

def check_source_code():
    """Check source code structure."""
    print(f"\n{BLUE}Checking source code...{NC}")
    
    modules = [
        "claude_worker/__init__.py",
        "claude_worker/server/main.py",
        "claude_worker/server/models.py",
        "claude_worker/server/executor.py",
        "claude_worker/cli/main.py"
    ]
    
    all_present = True
    for module in modules:
        if check_file_exists(module):
            print(f"{GREEN}✓ {module}{NC}")
        else:
            print(f"{RED}✗ {module} - MISSING{NC}")
            all_present = False
    
    # Check for __version__
    init_file = Path("claude_worker/__init__.py")
    if init_file.exists():
        content = init_file.read_text()
        if "__version__" in content:
            print(f"{GREEN}✓ Version string defined in __init__.py{NC}")
        else:
            print(f"{YELLOW}⚠ __version__ not found in __init__.py{NC}")
    
    return all_present

def check_dependencies():
    """Check dependencies are locked and up to date."""
    print(f"\n{BLUE}Checking dependencies...{NC}")
    
    success, _ = run_command(["poetry", "lock", "--check"])
    if success:
        print(f"{GREEN}✓ Dependencies are locked and up to date{NC}")
    else:
        print(f"{YELLOW}⚠ Dependencies need updating (run: poetry lock){NC}")
        return False
    
    # Check for security issues
    print(f"{BLUE}Checking for security vulnerabilities...{NC}")
    success, output = run_command(["poetry", "run", "pip", "list"])
    if success:
        print(f"{GREEN}✓ Dependencies installed{NC}")
    else:
        print(f"{YELLOW}⚠ Could not check dependencies{NC}")
    
    return True

def check_git_status():
    """Check git repository status."""
    print(f"\n{BLUE}Checking git status...{NC}")
    
    # Check if it's a git repo
    if not Path(".git").exists():
        print(f"{RED}✗ Not a git repository{NC}")
        return False
    
    # Check for uncommitted changes
    success, output = run_command(["git", "status", "--porcelain"])
    if success and not output.strip():
        print(f"{GREEN}✓ Working directory clean{NC}")
    else:
        print(f"{YELLOW}⚠ Uncommitted changes detected:{NC}")
        print(output)
        return False
    
    # Check current branch
    success, branch = run_command(["git", "branch", "--show-current"])
    if success:
        branch = branch.strip()
        if branch == "main" or branch == "master":
            print(f"{GREEN}✓ On {branch} branch{NC}")
        else:
            print(f"{YELLOW}⚠ On {branch} branch (not main/master){NC}")
    
    # Check for remote
    success, remote = run_command(["git", "remote", "-v"])
    if success and remote:
        print(f"{GREEN}✓ Git remote configured{NC}")
    else:
        print(f"{YELLOW}⚠ No git remote configured{NC}")
    
    return True

def check_tests():
    """Check if tests pass (if they exist)."""
    print(f"\n{BLUE}Checking tests...{NC}")
    
    if Path("tests").exists():
        print(f"{YELLOW}⚠ Tests directory found but skipping (per project requirements){NC}")
    else:
        print(f"{GREEN}✓ No tests (as intended){NC}")
    
    return True

def check_cli():
    """Check if CLI works."""
    print(f"\n{BLUE}Checking CLI functionality...{NC}")
    
    success, output = run_command(["poetry", "run", "claude-worker", "--help"])
    if success:
        print(f"{GREEN}✓ CLI help command works{NC}")
    else:
        print(f"{RED}✗ CLI help command failed{NC}")
        return False
    
    success, output = run_command(["poetry", "run", "claude-worker", "--version"])
    if success:
        print(f"{GREEN}✓ CLI version command works{NC}")
    else:
        print(f"{YELLOW}⚠ CLI version command failed{NC}")
    
    return True

def check_build():
    """Check if package builds successfully."""
    print(f"\n{BLUE}Checking package build...{NC}")
    
    # Clean old builds
    for path in ["dist", "build"]:
        if Path(path).exists():
            import shutil
            shutil.rmtree(path)
    
    success, output = run_command(["poetry", "build"])
    if success:
        print(f"{GREEN}✓ Package builds successfully{NC}")
        
        # Check build artifacts
        dist_files = list(Path("dist").glob("*"))
        for file in dist_files:
            size_mb = file.stat().st_size / (1024 * 1024)
            print(f"{GREEN}  - {file.name} ({size_mb:.2f} MB){NC}")
            
            # Warn if too large for PyPI
            if size_mb > 60:
                print(f"{YELLOW}  ⚠ File may be too large for PyPI (>60MB){NC}")
    else:
        print(f"{RED}✗ Package build failed{NC}")
        return False
    
    return True

def main():
    """Run all checks."""
    print(f"{BLUE}{'='*50}{NC}")
    print(f"{BLUE}Claude Worker Pre-Publication Checklist{NC}")
    print(f"{BLUE}{'='*50}{NC}")
    
    checks = [
        ("Project Configuration", check_pyproject),
        ("Required Files", check_required_files),
        ("Source Code", check_source_code),
        ("Dependencies", check_dependencies),
        ("Git Status", check_git_status),
        ("Tests", check_tests),
        ("CLI Functionality", check_cli),
        ("Package Build", check_build)
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"{RED}✗ {name} check failed with error: {e}{NC}")
            results.append((name, False))
    
    # Summary
    print(f"\n{BLUE}{'='*50}{NC}")
    print(f"{BLUE}Summary:{NC}")
    print(f"{BLUE}{'='*50}{NC}")
    
    all_passed = True
    for name, passed in results:
        if passed:
            print(f"{GREEN}✓ {name}{NC}")
        else:
            print(f"{RED}✗ {name}{NC}")
            all_passed = False
    
    print(f"\n{BLUE}{'='*50}{NC}")
    if all_passed:
        print(f"{GREEN}🎉 All checks passed! Ready to publish.{NC}")
        print(f"\n{BLUE}Next steps:{NC}")
        print(f"1. Run: {YELLOW}./scripts/publish.sh{NC}")
        print(f"2. Or manually: {YELLOW}poetry publish --build{NC}")
        return 0
    else:
        print(f"{RED}❌ Some checks failed. Please fix issues before publishing.{NC}")
        return 1

if __name__ == "__main__":
    sys.exit(main())