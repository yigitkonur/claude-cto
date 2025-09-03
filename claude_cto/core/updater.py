"""
SOLE RESPONSIBILITY: Handle version checking and upgrade operations for claude-cto.
Provides utilities for checking PyPI for latest versions and coordinating upgrades.
"""

import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from packaging import version

import httpx

from claude_cto import __version__


class VersionChecker:
    """
    Handles version checking against PyPI API.
    Implements caching to avoid excessive API calls.
    """
    
    def __init__(self, package_name: str = "claude-cto", cache_duration: int = 300):
        """
        Initialize version checker.
        
        Args:
            package_name: Name of the package on PyPI
            cache_duration: Cache duration in seconds (default: 5 minutes)
        """
        self.package_name = package_name
        self.cache_duration = cache_duration
        self.cache_file = Path.home() / ".claude-cto" / "version_cache.json"
        
        # Ensure cache directory exists
        self.cache_file.parent.mkdir(exist_ok=True)
    
    def get_current_version(self) -> str:
        """Get the currently installed version."""
        return __version__
    
    def get_latest_version_from_pypi(self) -> Optional[str]:
        """
        Fetch the latest version from PyPI API.
        
        Returns:
            Latest version string, or None if fetch failed
        """
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"https://pypi.org/pypi/{self.package_name}/json")
                response.raise_for_status()
                data = response.json()
                return data["info"]["version"]
        except (httpx.RequestError, httpx.HTTPStatusError, KeyError):
            return None
    
    def _load_cache(self) -> Optional[Dict[str, Any]]:
        """Load version cache from disk."""
        try:
            if not self.cache_file.exists():
                return None
            
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Check if cache is expired
            cache_time = cache_data.get("timestamp", 0)
            if time.time() - cache_time > self.cache_duration:
                return None
            
            return cache_data
        except (json.JSONDecodeError, OSError):
            return None
    
    def _save_cache(self, latest_version: str) -> None:
        """Save version cache to disk."""
        try:
            cache_data = {
                "timestamp": time.time(),
                "latest_version": latest_version,
                "current_version": self.get_current_version(),
                "last_check": datetime.now().isoformat()
            }
            
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f)
        except OSError:
            pass  # Ignore cache write failures
    
    def get_latest_version(self, force_refresh: bool = False) -> Optional[str]:
        """
        Get the latest version, using cache if available.
        
        Args:
            force_refresh: If True, bypass cache and fetch from PyPI
            
        Returns:
            Latest version string, or None if unavailable
        """
        if not force_refresh:
            cache_data = self._load_cache()
            if cache_data:
                return cache_data.get("latest_version")
        
        # Fetch from PyPI
        latest_version = self.get_latest_version_from_pypi()
        if latest_version:
            self._save_cache(latest_version)
        
        return latest_version
    
    def is_update_available(self, force_refresh: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check if an update is available.
        
        Args:
            force_refresh: If True, bypass cache and fetch from PyPI
            
        Returns:
            Tuple of (update_available, current_version, latest_version)
        """
        current_ver = self.get_current_version()
        latest_ver = self.get_latest_version(force_refresh=force_refresh)
        
        if latest_ver is None:
            return False, current_ver, None
        
        try:
            is_newer = version.parse(latest_ver) > version.parse(current_ver)
            return is_newer, current_ver, latest_ver
        except version.InvalidVersion:
            # If version parsing fails, assume no update available
            return False, current_ver, latest_ver
    
    def should_check_for_updates(self, frequency: str) -> bool:
        """
        Check if we should check for updates based on frequency setting and last check time.
        
        Args:
            frequency: "daily", "weekly", or "never"
            
        Returns:
            True if we should check for updates
        """
        if frequency == "never":
            return False
        
        cache_data = self._load_cache()
        if cache_data is None:
            return True  # No cache, so check
        
        last_check_str = cache_data.get("last_check")
        if not last_check_str:
            return True  # No last check time, so check
        
        try:
            last_check = datetime.fromisoformat(last_check_str)
            now = datetime.now()
            
            if frequency == "daily":
                return now - last_check >= timedelta(days=1)
            elif frequency == "weekly":
                return now - last_check >= timedelta(days=7)
            else:
                return True  # Unknown frequency, default to checking
                
        except ValueError:
            return True  # Invalid date format, default to checking


class PackageUpgrader:
    """
    Handles the actual upgrade process for claude-cto.
    Detects installation method and performs appropriate upgrade.
    """
    
    def __init__(self):
        self.version_checker = VersionChecker()
    
    def detect_installation_method(self) -> str:
        """
        Detect how claude-cto was installed.
        
        Returns:
            Installation method: 'pip', 'uv', 'poetry', or 'unknown'
        """
        # Check if we can find pip
        try:
            subprocess.run([sys.executable, "-m", "pip", "--version"], 
                         capture_output=True, check=True, timeout=5)
            return "pip"
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Check for uv
        try:
            subprocess.run(["uv", "--version"], 
                         capture_output=True, check=True, timeout=5)
            return "uv"
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Check for poetry (look for pyproject.toml in site-packages parent)
        try:
            import claude_cto
            package_path = Path(claude_cto.__file__).parent
            # Look for poetry indicators
            possible_project_roots = [package_path.parent, package_path.parent.parent]
            for root in possible_project_roots:
                if (root / "pyproject.toml").exists():
                    with open(root / "pyproject.toml", 'r') as f:
                        content = f.read()
                        if "[tool.poetry" in content:
                            return "poetry"
        except Exception:
            pass
        
        return "unknown"
    
    def upgrade_package(self, method: Optional[str] = None) -> Tuple[bool, str]:
        """
        Upgrade claude-cto package.
        
        Args:
            method: Installation method override ('pip', 'uv', 'poetry')
            
        Returns:
            Tuple of (success, message)
        """
        if method is None:
            method = self.detect_installation_method()
        
        try:
            if method == "pip":
                result = subprocess.run([
                    sys.executable, "-m", "pip", "install", "--upgrade", "claude-cto"
                ], capture_output=True, text=True, timeout=120)
                
            elif method == "uv":
                result = subprocess.run([
                    "uv", "pip", "install", "--upgrade", "claude-cto"
                ], capture_output=True, text=True, timeout=120)
                
            elif method == "poetry":
                result = subprocess.run([
                    "poetry", "add", "claude-cto@latest"
                ], capture_output=True, text=True, timeout=120)
                
            else:
                return False, f"Unknown installation method: {method}. Please upgrade manually using pip install --upgrade claude-cto"
            
            if result.returncode == 0:
                return True, f"Successfully upgraded claude-cto using {method}"
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                return False, f"Upgrade failed using {method}: {error_msg}"
                
        except subprocess.TimeoutExpired:
            return False, f"Upgrade timed out using {method}"
        except Exception as e:
            return False, f"Upgrade error using {method}: {str(e)}"
    
    def check_and_upgrade(self, force: bool = False, auto: bool = False) -> Tuple[bool, str]:
        """
        Check for updates and optionally upgrade.
        
        Args:
            force: Force upgrade even if no update detected
            auto: Automatic upgrade without confirmation (use carefully)
            
        Returns:
            Tuple of (action_taken, message)
        """
        # Check for updates
        update_available, current_ver, latest_ver = self.version_checker.is_update_available(force_refresh=True)
        
        if not force and not update_available:
            if latest_ver is None:
                return False, "Could not check for updates (network error)"
            return False, f"Already up to date (current: {current_ver}, latest: {latest_ver})"
        
        if not auto and not force:
            # This would normally prompt user, but we'll return info for CLI to handle
            return False, f"Update available: {current_ver} -> {latest_ver}"
        
        # Perform upgrade
        success, message = self.upgrade_package()
        return success, message