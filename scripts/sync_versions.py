#!/usr/bin/env python3
"""
Version synchronization script to ensure consistency across all version files.
Prevents version conflicts by checking and updating all version references.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import subprocess
import argparse

class VersionSynchronizer:
    """Manages version synchronization across all project files."""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.version_files = {
            'pyproject.toml': [
                (r'^version = "([\d.]+)"', 'version = "{version}"'),
                (r'^version = "([\d.]+)"', 'version = "{version}"', 103, 105)  # Poetry section
            ],
            'claude_cto/__init__.py': [
                (r'^__version__ = "([\d.]+)"', '__version__ = "{version}"')
            ],
            'smithery.yaml': [
                (r'^version: ([\d.]+)', 'version: {version}')
            ]
        }
        
    def get_current_versions(self) -> Dict[str, List[str]]:
        """Extract current version from all files."""
        versions = {}
        
        for file_path, patterns in self.version_files.items():
            full_path = self.project_root / file_path
            if not full_path.exists():
                print(f"⚠️  File not found: {file_path}")
                continue
                
            content = full_path.read_text()
            file_versions = []
            
            for pattern_info in patterns:
                if isinstance(pattern_info, tuple) and len(pattern_info) == 4:
                    pattern, _, start_line, end_line = pattern_info
                    lines = content.split('\n')
                    for i in range(start_line - 1, min(end_line, len(lines))):
                        match = re.match(pattern, lines[i])
                        if match:
                            file_versions.append(match.group(1))
                else:
                    pattern = pattern_info[0] if isinstance(pattern_info, tuple) else pattern_info
                    for match in re.finditer(pattern, content, re.MULTILINE):
                        file_versions.append(match.group(1))
            
            if file_versions:
                versions[file_path] = file_versions
                
        return versions
    
    def get_git_tags(self) -> List[str]:
        """Get all git tags."""
        try:
            result = subprocess.run(
                ['git', 'tag', '-l', 'v*'],
                capture_output=True,
                text=True,
                check=True
            )
            return sorted(result.stdout.strip().split('\n')) if result.stdout else []
        except subprocess.CalledProcessError:
            return []
    
    def get_latest_remote_version(self) -> Optional[str]:
        """Get latest version from remote repository."""
        try:
            # Fetch latest tags from remote
            subprocess.run(['git', 'fetch', '--tags'], capture_output=True, check=True)
            
            # Get latest tag
            result = subprocess.run(
                ['git', 'describe', '--tags', '--abbrev=0', 'origin/main'],
                capture_output=True,
                text=True,
                check=True
            )
            tag = result.stdout.strip()
            return tag.lstrip('v') if tag else None
        except subprocess.CalledProcessError:
            return None
    
    def check_conflicts(self) -> Tuple[bool, str]:
        """Check for version conflicts across files."""
        versions = self.get_current_versions()
        
        if not versions:
            return False, "No version files found"
        
        # Get all unique versions
        all_versions = set()
        for file_versions in versions.values():
            all_versions.update(file_versions)
        
        if len(all_versions) > 1:
            conflict_msg = "Version conflicts detected:\n"
            for file_path, file_versions in versions.items():
                conflict_msg += f"  {file_path}: {', '.join(file_versions)}\n"
            return False, conflict_msg
        
        current_version = next(iter(all_versions))
        
        # Check against remote
        remote_version = self.get_latest_remote_version()
        if remote_version and remote_version != current_version:
            return False, f"Local version ({current_version}) differs from remote ({remote_version})"
        
        return True, f"All files synchronized at version {current_version}"
    
    def update_version(self, new_version: str, force: bool = False) -> bool:
        """Update version in all files."""
        # Remove 'v' prefix if present
        new_version = new_version.lstrip('v')
        
        # Check for conflicts first
        if not force:
            is_synced, message = self.check_conflicts()
            if not is_synced and "differs from remote" in message:
                print(f"❌ {message}")
                print("Use --force to override or sync with remote first")
                return False
        
        success = True
        for file_path, patterns in self.version_files.items():
            full_path = self.project_root / file_path
            if not full_path.exists():
                print(f"⚠️  Skipping missing file: {file_path}")
                continue
            
            content = full_path.read_text()
            original_content = content
            
            for pattern_info in patterns:
                if isinstance(pattern_info, tuple):
                    if len(pattern_info) == 4:
                        pattern, replacement, start_line, end_line = pattern_info
                        lines = content.split('\n')
                        for i in range(start_line - 1, min(end_line, len(lines))):
                            if re.match(pattern, lines[i]):
                                lines[i] = replacement.format(version=new_version)
                        content = '\n'.join(lines)
                    else:
                        pattern, replacement = pattern_info[:2]
                        content = re.sub(
                            pattern,
                            replacement.format(version=new_version),
                            content,
                            flags=re.MULTILINE
                        )
            
            if content != original_content:
                full_path.write_text(content)
                print(f"✅ Updated {file_path} to version {new_version}")
            else:
                print(f"⚠️  No changes needed in {file_path}")
                
        return success
    
    def sync_with_remote(self) -> bool:
        """Sync local version with remote."""
        remote_version = self.get_latest_remote_version()
        if not remote_version:
            print("❌ Could not determine remote version")
            return False
        
        print(f"📦 Syncing with remote version: {remote_version}")
        return self.update_version(remote_version, force=True)
    
    def validate(self) -> bool:
        """Validate version consistency."""
        is_synced, message = self.check_conflicts()
        
        if is_synced:
            print(f"✅ {message}")
            
            # Also check git tags
            versions = self.get_current_versions()
            if versions:
                current_version = next(iter(next(iter(versions.values()))))
                git_tags = self.get_git_tags()
                expected_tag = f"v{current_version}"
                
                if expected_tag in git_tags:
                    print(f"✅ Git tag {expected_tag} exists")
                else:
                    print(f"⚠️  Git tag {expected_tag} not found")
                    print(f"   Available tags: {', '.join(git_tags[-5:])}")
        else:
            print(f"❌ {message}")
            
        return is_synced


def main():
    parser = argparse.ArgumentParser(description='Synchronize version across project files')
    parser.add_argument('--check', action='store_true', help='Check for version conflicts')
    parser.add_argument('--sync', action='store_true', help='Sync with remote version')
    parser.add_argument('--update', type=str, help='Update to specific version')
    parser.add_argument('--force', action='store_true', help='Force update even with conflicts')
    parser.add_argument('--validate', action='store_true', help='Validate version consistency')
    
    args = parser.parse_args()
    
    synchronizer = VersionSynchronizer()
    
    # Default to validate if no action specified
    if not any([args.check, args.sync, args.update, args.validate]):
        args.validate = True
    
    if args.check:
        is_synced, message = synchronizer.check_conflicts()
        print(message)
        sys.exit(0 if is_synced else 1)
    
    if args.sync:
        success = synchronizer.sync_with_remote()
        sys.exit(0 if success else 1)
    
    if args.update:
        success = synchronizer.update_version(args.update, force=args.force)
        sys.exit(0 if success else 1)
    
    if args.validate:
        is_valid = synchronizer.validate()
        sys.exit(0 if is_valid else 1)


if __name__ == '__main__':
    main()