#!/usr/bin/env python3
"""
Enhanced version bumping script with conflict detection and recovery.
"""

import re
import sys
import json
import subprocess
from pathlib import Path
from typing import Tuple, Optional
import argparse

# Paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent
INIT_FILE = PROJECT_ROOT / "claude_cto" / "__init__.py"
PYPROJECT_FILE = PROJECT_ROOT / "pyproject.toml"
SMITHERY_FILE = PROJECT_ROOT / "smithery.yaml"
VERSION_INFO_FILE = PROJECT_ROOT / ".version_info.json"


def check_git_status() -> bool:
    """Check if git working directory is clean."""
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            check=True,
            cwd=PROJECT_ROOT
        )
        return len(result.stdout.strip()) == 0
    except subprocess.CalledProcessError:
        return False


def fetch_remote_tags() -> bool:
    """Fetch latest tags from remote."""
    try:
        subprocess.run(
            ['git', 'fetch', '--tags', '--prune'],
            capture_output=True,
            check=True,
            cwd=PROJECT_ROOT
        )
        return True
    except subprocess.CalledProcessError:
        return False


def get_remote_version() -> Optional[str]:
    """Get latest version from remote repository."""
    try:
        # First fetch to ensure we have latest
        subprocess.run(
            ['git', 'fetch', 'origin', 'main'],
            capture_output=True,
            check=True,
            cwd=PROJECT_ROOT
        )
        
        # Get latest tag from remote
        result = subprocess.run(
            ['git', 'describe', '--tags', '--abbrev=0', 'origin/main'],
            capture_output=True,
            text=True,
            check=True,
            cwd=PROJECT_ROOT
        )
        tag = result.stdout.strip()
        return tag.lstrip('v') if tag else None
    except subprocess.CalledProcessError:
        return None


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


def check_version_conflicts() -> Tuple[bool, str]:
    """Check for version conflicts across all files."""
    versions = {}
    
    # Check __init__.py
    if INIT_FILE.exists():
        content = INIT_FILE.read_text()
        match = re.search(r'__version__ = ["\']([^"\']+)["\']', content)
        if match:
            versions['__init__.py'] = match.group(1)
    
    # Check pyproject.toml - both sections
    if PYPROJECT_FILE.exists():
        content = PYPROJECT_FILE.read_text()
        # Check [project] section
        match = re.search(r'\[project\][^[]*?version = ["\']([^"\']+)["\']', content, re.DOTALL)
        if match:
            versions['pyproject.toml [project]'] = match.group(1)
        # Check [tool.poetry] section
        match = re.search(r'\[tool\.poetry\][^[]*?version = ["\']([^"\']+)["\']', content, re.DOTALL)
        if match:
            versions['pyproject.toml [tool.poetry]'] = match.group(1)
    
    # Check smithery.yaml
    if SMITHERY_FILE.exists():
        content = SMITHERY_FILE.read_text()
        match = re.search(r'^version:\s*(.+)$', content, re.MULTILINE)
        if match:
            versions['smithery.yaml'] = match.group(1)
    
    # Check for conflicts
    unique_versions = set(versions.values())
    if len(unique_versions) > 1:
        conflict_msg = "Version conflicts detected:\n"
        for file, version in versions.items():
            conflict_msg += f"  {file}: {version}\n"
        return False, conflict_msg
    elif len(unique_versions) == 1:
        return True, f"All files synchronized at version {next(iter(unique_versions))}"
    else:
        return False, "No version found in any files"


def update_all_files(new_version: str):
    """Update version in all files."""
    updated_files = []
    
    # Update __init__.py
    if INIT_FILE.exists():
        content = INIT_FILE.read_text()
        updated = re.sub(
            r'__version__ = ["\'][^"\']+["\']',
            f'__version__ = "{new_version}"',
            content
        )
        if updated != content:
            INIT_FILE.write_text(updated)
            updated_files.append(str(INIT_FILE.relative_to(PROJECT_ROOT)))
            print(f"✅ Updated {INIT_FILE.relative_to(PROJECT_ROOT)}")
    
    # Update pyproject.toml
    if PYPROJECT_FILE.exists():
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
        
        if updated != content:
            PYPROJECT_FILE.write_text(updated)
            updated_files.append(str(PYPROJECT_FILE.relative_to(PROJECT_ROOT)))
            print(f"✅ Updated {PYPROJECT_FILE.relative_to(PROJECT_ROOT)}")
    
    # Update smithery.yaml
    if SMITHERY_FILE.exists():
        content = SMITHERY_FILE.read_text()
        updated = re.sub(
            r'^version:\s*.+$',
            f'version: {new_version}',
            content,
            flags=re.MULTILINE
        )
        if updated != content:
            SMITHERY_FILE.write_text(updated)
            updated_files.append(str(SMITHERY_FILE.relative_to(PROJECT_ROOT)))
            print(f"✅ Updated {SMITHERY_FILE.relative_to(PROJECT_ROOT)}")
    
    return updated_files


def save_version_info(new_version: str, current_version: str, bump_type: Optional[str] = None):
    """Save version info for workflows."""
    version_info = {
        'version': new_version,
        'previous_version': current_version,
        'bump_type': bump_type,
        'remote_version': get_remote_version()
    }
    
    VERSION_INFO_FILE.write_text(json.dumps(version_info, indent=2))
    print(f"📝 Saved version info to {VERSION_INFO_FILE.relative_to(PROJECT_ROOT)}")


def git_operations(new_version: str, updated_files: list, create_tag: bool = True, ci_mode: bool = False):
    """Handle git operations for version bump."""
    # Check if we're in a git repo
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError:
        print("⚠️  Not in a git repository, skipping git operations")
        return
    
    # Add and commit version files
    files_to_add = [PROJECT_ROOT / f for f in updated_files]
    if VERSION_INFO_FILE.exists():
        files_to_add.append(VERSION_INFO_FILE)
    
    subprocess.run(["git", "add"] + [str(f) for f in files_to_add], cwd=PROJECT_ROOT, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"chore: bump version to v{new_version}"],
        cwd=PROJECT_ROOT,
        check=True
    )
    print(f"✅ Committed version bump to v{new_version}")
    
    if create_tag:
        # Check if tag already exists
        try:
            result = subprocess.run(
                ["git", "tag", "-l", f"v{new_version}"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=True
            )
            if result.stdout.strip():
                print(f"⚠️  Tag v{new_version} already exists locally")
            else:
                subprocess.run(["git", "tag", f"v{new_version}"], cwd=PROJECT_ROOT, check=True)
                print(f"✅ Created git tag v{new_version}")
        except subprocess.CalledProcessError:
            pass
        
        print(f"\n🚀 To trigger release pipeline, run:")
        print(f"   git push origin main")
        print(f"   git push origin v{new_version}")


def main():
    """Main version bumping logic with enhanced conflict detection."""
    parser = argparse.ArgumentParser(
        description='Enhanced version bumping with conflict detection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s patch                    # Bump patch version
  %(prog)s minor --sync              # Sync with remote then bump minor
  %(prog)s 1.0.0 --force            # Force specific version
  %(prog)s patch --ci               # CI mode (non-interactive)
  %(prog)s --check                  # Check for conflicts only
"""
    )
    
    parser.add_argument(
        'bump_type',
        nargs='?',
        help='Type of bump (major/minor/patch) or specific version'
    )
    parser.add_argument('--ci', action='store_true', help='Run in CI mode (no prompts)')
    parser.add_argument('--force', action='store_true', help='Force bump even with conflicts')
    parser.add_argument('--sync', action='store_true', help='Sync with remote before bumping')
    parser.add_argument('--check', action='store_true', help='Check for conflicts only')
    parser.add_argument('--no-tag', action='store_true', help="Don't create git tag")
    parser.add_argument('--no-commit', action='store_true', help="Don't commit changes")
    
    args = parser.parse_args()
    
    # Check conflicts mode
    if args.check:
        is_synced, message = check_version_conflicts()
        print(message)
        
        remote_version = get_remote_version()
        current_version = get_current_version()
        if remote_version and remote_version != current_version:
            print(f"⚠️  Remote version: {remote_version}")
        
        sys.exit(0 if is_synced else 1)
    
    # Require bump_type if not just checking
    if not args.bump_type:
        parser.error("bump_type is required unless using --check")
    
    # Check git status
    if not args.force and not args.ci and not args.no_commit:
        if not check_git_status():
            print("❌ Git working directory is not clean")
            print("   Commit or stash changes before bumping version")
            print("   Or use --no-commit to skip git operations")
            sys.exit(1)
    
    # Check for version conflicts
    is_synced, conflict_msg = check_version_conflicts()
    if not is_synced and not args.force:
        print(f"❌ {conflict_msg}")
        print("   Use --force to override")
        sys.exit(1)
    
    # Sync with remote if requested
    if args.sync:
        print("📡 Fetching remote tags...")
        if not fetch_remote_tags():
            print("❌ Failed to fetch remote tags")
            if not args.force:
                sys.exit(1)
    
    # Get current version
    try:
        current_version = get_current_version()
        print(f"Current version: {current_version}")
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    # Check for remote conflicts
    remote_version = get_remote_version()
    if remote_version and not args.force:
        remote_parts = parse_version(remote_version)
        current_parts = parse_version(current_version)
        
        if remote_parts > current_parts:
            print(f"❌ Remote version ({remote_version}) is ahead of local ({current_version})")
            print("   Use --sync to update or --force to override")
            sys.exit(1)
        elif remote_parts < current_parts:
            print(f"⚠️  Local version ({current_version}) is ahead of remote ({remote_version})")
    
    # Determine new version
    if args.bump_type in ["major", "minor", "patch"]:
        new_version = bump_version(current_version, args.bump_type)
        print(f"Bumping {args.bump_type} version: {current_version} → {new_version}")
        bump_type = args.bump_type
    else:
        # Specific version provided
        new_version = args.bump_type
        try:
            parse_version(new_version)  # Validate format
            print(f"Setting specific version: {current_version} → {new_version}")
            bump_type = None
        except ValueError as e:
            print(f"❌ {e}")
            sys.exit(1)
    
    # Check if version already exists as tag
    if not args.force:
        try:
            result = subprocess.run(
                ['git', 'tag', '-l', f'v{new_version}'],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=True
            )
            if result.stdout.strip():
                print(f"❌ Version {new_version} already exists as tag")
                print("   Use --force to override")
                sys.exit(1)
        except subprocess.CalledProcessError:
            pass
    
    # Confirm the change (skip in CI mode)
    if not args.ci:
        response = input(f"Proceed with version {new_version}? (Y/n): ")
        if response.lower() == 'n':
            print("Aborted")
            sys.exit(0)
    else:
        print(f"CI mode: Proceeding with version {new_version}")
    
    # Update files
    updated_files = update_all_files(new_version)
    
    # Save version info for workflows
    save_version_info(new_version, current_version, bump_type)
    
    # Git operations
    if not args.no_commit:
        git_operations(
            new_version,
            updated_files,
            create_tag=not args.no_tag,
            ci_mode=args.ci
        )
    
    print(f"\n🎉 Version successfully bumped to {new_version}!")
    
    if args.no_commit:
        print("\n📝 Next steps:")
        print("1. Review changes: git diff")
        print(f"2. Commit: git commit -am 'chore: bump version to v{new_version}'")
        if not args.no_tag:
            print(f"3. Tag: git tag v{new_version}")
        print("4. Push: git push origin main && git push origin --tags")
    else:
        print("\n📝 Next steps:")
        print("1. Test the changes locally")
        print("2. Push to trigger CI/CD: git push origin main && git push origin --tags")
        print("3. Monitor the release pipeline in GitHub Actions")


if __name__ == "__main__":
    main()