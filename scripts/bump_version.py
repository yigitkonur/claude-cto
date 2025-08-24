#!/usr/bin/env python3
"""
Automated version bumping script for claude-cto.
Syncs version across __init__.py, pyproject.toml, and creates git tags.
"""

import re
import sys
import subprocess
from pathlib import Path
from typing import Tuple

# Paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent
INIT_FILE = PROJECT_ROOT / "claude_cto" / "__init__.py"
PYPROJECT_FILE = PROJECT_ROOT / "pyproject.toml"


def get_current_version() -> str:
    """Get current version from __init__.py"""
    content = INIT_FILE.read_text()
    match = re.search(r'__version__ = ["\']([^"\']+)["\']', content)
    if not match:
        raise ValueError("Could not find __version__ in __init__.py")
    return match.group(1)


def parse_version(version: str) -> Tuple[int, int, int]:
    """Parse semantic version string into major.minor.patch"""
    try:
        parts = version.split('.')
        return int(parts[0]), int(parts[1]), int(parts[2])
    except (ValueError, IndexError):
        raise ValueError(f"Invalid version format: {version}. Use major.minor.patch")


def bump_version(version: str, bump_type: str) -> str:
    """Bump version by type (major, minor, patch)"""
    major, minor, patch = parse_version(version)
    
    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError("bump_type must be 'major', 'minor', or 'patch'")


def update_init_file(new_version: str):
    """Update version in __init__.py"""
    content = INIT_FILE.read_text()
    updated = re.sub(
        r'__version__ = ["\'][^"\']+["\']',
        f'__version__ = "{new_version}"',
        content
    )
    INIT_FILE.write_text(updated)
    print(f"✅ Updated {INIT_FILE.relative_to(PROJECT_ROOT)}")


def update_pyproject_file(new_version: str):
    """Update version in pyproject.toml"""
    content = PYPROJECT_FILE.read_text()
    
    # Update project version in [project] section
    updated = re.sub(
        r'(\[project\][^[]*?)version = ["\'][^"\']+["\']',
        rf'\1version = "{new_version}"',
        content,
        flags=re.DOTALL
    )
    
    # Update project version in [tool.poetry] section  
    updated = re.sub(
        r'(\[tool\.poetry\][^[]*?)version = ["\'][^"\']+["\']',
        rf'\1version = "{new_version}"',
        updated,
        flags=re.DOTALL
    )
    
    PYPROJECT_FILE.write_text(updated)
    print(f"✅ Updated {PYPROJECT_FILE.relative_to(PROJECT_ROOT)}")


def run_command(cmd: list, check: bool = True) -> subprocess.CompletedProcess:
    """Run shell command with error handling"""
    try:
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, check=check)
        return result
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {' '.join(cmd)}")
        print(f"   Error: {e.stderr.strip()}")
        if check:
            sys.exit(1)
        return e


def git_operations(new_version: str, create_tag: bool = True, ci_mode: bool = False):
    """Handle git operations for version bump"""
    # Check if we're in a git repo
    result = run_command(["git", "status", "--porcelain"], check=False)
    if result.returncode != 0:
        print("⚠️  Not in a git repository, skipping git operations")
        return
    
    # Check for uncommitted changes (allow in CI mode)
    if result.stdout.strip():
        print("⚠️  You have uncommitted changes:")
        print(result.stdout)
        
        # In CI mode, we might expect uncommitted changes from version bumping
        import os
        if not (os.getenv('GITHUB_ACTIONS') or ci_mode):
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                print("Aborted")
                sys.exit(1)
    
    # Add and commit version files
    run_command(["git", "add", str(INIT_FILE), str(PYPROJECT_FILE)])
    run_command(["git", "commit", "-m", f"chore: bump version to v{new_version}"])
    print(f"✅ Committed version bump to v{new_version}")
    
    if create_tag:
        # Create git tag
        run_command(["git", "tag", f"v{new_version}"])
        print(f"✅ Created git tag v{new_version}")
        
        print(f"\n🚀 To trigger release pipeline, run:")
        print(f"   git push origin main")
        print(f"   git push origin v{new_version}")


def main():
    """Main version bumping logic"""
    if len(sys.argv) < 2:
        print("Usage: python scripts/bump_version.py <bump_type|version> [--no-tag] [--ci]")
        print("")
        print("Arguments:")
        print("  bump_type    'major', 'minor', or 'patch'")
        print("  version      Specific version (e.g., '1.2.3')")
        print("  --no-tag     Don't create git tag")
        print("  --ci         Run in CI mode (non-interactive)")
        print("")
        print("Examples:")
        print("  python scripts/bump_version.py patch")
        print("  python scripts/bump_version.py minor") 
        print("  python scripts/bump_version.py 1.0.0")
        print("  python scripts/bump_version.py patch --no-tag")
        print("  python scripts/bump_version.py patch --ci")
        sys.exit(1)
    
    arg = sys.argv[1]
    create_tag = "--no-tag" not in sys.argv
    ci_mode = "--ci" in sys.argv
    
    current_version = get_current_version()
    print(f"Current version: {current_version}")
    
    # Determine new version
    if arg in ["major", "minor", "patch"]:
        new_version = bump_version(current_version, arg)
        print(f"Bumping {arg} version: {current_version} → {new_version}")
    else:
        # Specific version provided
        new_version = arg
        try:
            parse_version(new_version)  # Validate format
            print(f"Setting specific version: {current_version} → {new_version}")
        except ValueError as e:
            print(f"❌ {e}")
            sys.exit(1)
    
    # Confirm the change (skip in CI mode)
    if not ci_mode:
        response = input(f"Proceed with version {new_version}? (Y/n): ")
        if response.lower() == 'n':
            print("Aborted")
            sys.exit(0)
    else:
        print(f"CI mode: Proceeding with version {new_version}")
    
    # Update files
    update_init_file(new_version)
    update_pyproject_file(new_version)
    
    # Git operations
    git_operations(new_version, create_tag, ci_mode)
    
    print(f"\n🎉 Version successfully bumped to {new_version}!")
    print("\n📝 Next steps:")
    print("1. Test the changes locally")
    print("2. Push to trigger CI/CD: git push origin main && git push origin --tags")
    print("3. Monitor the release pipeline in GitHub Actions")


if __name__ == "__main__":
    main()