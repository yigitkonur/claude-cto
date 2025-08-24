"""
SOLE RESPONSIBILITY: Cross-platform path utilities for generating safe, unique filenames.
Handles directory context, special characters, and collision avoidance.
"""

import re
import hashlib
import unicodedata
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple


def sanitize_filename(filename: str, max_length: int = 50) -> str:
    """
    Convert any string to a safe, cross-platform filename component.

    Args:
        filename: Raw string to sanitize
        max_length: Maximum length for the sanitized component

    Returns:
        Safe filename component suitable for Windows/Linux/macOS
    """
    # Handle None or empty strings
    if not filename:
        return "unknown"

    # Convert to string and normalize unicode
    filename = str(filename)
    filename = unicodedata.normalize("NFKD", filename)

    # Convert to ASCII, removing accents
    filename = filename.encode("ascii", "ignore").decode("ascii")

    # character replacement map for cross-platform safety: removes Windows forbidden chars, Unix specials, and shell metacharacters
    replacements = {
        " ": "_",  # Spaces to underscores
        "-": "_",  # Hyphens to underscores
        ".": "",  # Remove dots (except extension)
        "/": "_",  # Forward slashes
        "\\": "_",  # Backslashes
        ":": "",  # Colons (Windows drive letters)
        "*": "",  # Wildcards
        "?": "",  # Question marks
        '"': "",  # Quotes
        "<": "",  # Less than
        ">": "",  # Greater than
        "|": "",  # Pipes
        "!": "",  # Exclamation marks
        "@": "at",  # At symbols
        "#": "hash",  # Hash symbols
        "$": "dollar",  # Dollar signs
        "%": "pct",  # Percent signs
        "^": "",  # Carets
        "&": "and",  # Ampersands
        "(": "",  # Parentheses
        ")": "",
        "[": "",  # Brackets
        "]": "",
        "{": "",  # Braces
        "}": "",
        "=": "eq",  # Equals
        "+": "plus",  # Plus signs
    }

    for old, new in replacements.items():
        filename = filename.replace(old, new)

    # Remove any remaining non-alphanumeric characters except underscores
    filename = re.sub(r"[^a-zA-Z0-9_]", "", filename)

    # Remove multiple consecutive underscores
    filename = re.sub(r"_+", "_", filename)

    # Remove leading/trailing underscores
    filename = filename.strip("_")

    # Ensure it's not empty
    if not filename:
        filename = "unnamed"

    # Truncate if too long
    if len(filename) > max_length:
        filename = filename[:max_length].rstrip("_")

    # Ensure it doesn't start with a dot (hidden file on Unix)
    if filename.startswith("."):
        filename = "dot" + filename[1:]

    return filename.lower()


def extract_directory_context(working_directory: str) -> str:
    """
    Extract meaningful context from working directory for filename.

    Args:
        working_directory: Full path to working directory

    Returns:
        Safe, meaningful directory context string
    """
    try:
        # Windows UNC path handling: extracts meaningful share names from \\server\share\path format
        if working_directory.startswith("\\\\"):
            # UNC path: \\server\share\path
            parts = working_directory.split("\\")
            # Use share name as context
            if len(parts) > 3:
                directory_name = parts[3] if parts[3] else parts[2]
            else:
                directory_name = "network"
        else:
            path = Path(working_directory)

            # Try to resolve, but don't fail if it doesn't exist
            try:
                path = path.resolve()
            except (OSError, RuntimeError):
                # Path doesn't exist or can't be resolved
                pass

            # Get the last meaningful directory name
            directory_name = path.name

            # meaningful name extraction: avoids generic folder names by combining with parent directory
            if len(directory_name) <= 2 or directory_name.lower() in [
                "src",
                "app",
                "lib",
                "bin",
                "tmp",
                "dist",
                "build",
            ]:
                parent_name = path.parent.name
                # Check if parent is meaningful (not root or drive)
                if parent_name and not (
                    parent_name == ""  # Empty
                    or parent_name == path.anchor  # Unix root
                    or (len(parent_name) == 2 and parent_name[1] == ":")  # Windows drive
                ):
                    directory_name = f"{parent_name}_{directory_name}"

        # Sanitize the directory name
        safe_name = sanitize_filename(directory_name, max_length=30)

        return safe_name

    except Exception:
        # Fallback for any path resolution issues
        # Extract last part of path that looks meaningful
        import os

        basename = os.path.basename(working_directory) or "root"
        return sanitize_filename(basename, max_length=30)


def generate_log_filename(
    task_id: int,
    working_directory: str,
    log_type: str,
    timestamp: Optional[datetime] = None,
) -> str:
    """
    Generate a unique, descriptive log filename.

    Args:
        task_id: Task ID number
        working_directory: Working directory path
        log_type: Type of log ('summary', 'detailed', 'raw')
        timestamp: Optional timestamp (defaults to now)

    Returns:
        Safe, unique log filename

    Examples:
        task_1_myproject_20250821_1429_summary.log
        task_5_webapp_src_20250821_1430_detailed.log
    """
    if timestamp is None:
        timestamp = datetime.now()

    # Extract directory context
    dir_context = extract_directory_context(working_directory)

    # Format timestamp (YYYYMMDD_HHMM)
    time_str = timestamp.strftime("%Y%m%d_%H%M")

    # Sanitize log type
    safe_log_type = sanitize_filename(log_type, max_length=20)

    # collision-resistant naming: combines task ID, directory context, timestamp, and type for uniqueness
    filename = f"task_{task_id}_{dir_context}_{time_str}_{safe_log_type}.log"

    return filename


def generate_unique_session_id(working_directory: str, timestamp: Optional[datetime] = None) -> str:
    """
    Generate a unique session identifier for this working directory.

    Args:
        working_directory: Working directory path
        timestamp: Optional timestamp

    Returns:
        Unique session ID for database and logging context
    """
    if timestamp is None:
        timestamp = datetime.now()

    # Create a hash of the working directory
    dir_hash = hashlib.sha256(str(working_directory).encode()).hexdigest()[:8]

    # Get directory context
    dir_context = extract_directory_context(working_directory)

    # Format timestamp
    time_str = timestamp.strftime("%Y%m%d_%H%M%S")

    return f"{dir_context}_{time_str}_{dir_hash}"


def parse_log_filename(filename: str) -> Optional[Tuple[int, str, str, str]]:
    """
    Parse a log filename back into its components.

    Args:
        filename: Log filename to parse

    Returns:
        Tuple of (task_id, dir_context, timestamp, log_type) or None if invalid
    """
    try:
        # Remove .log extension
        name = filename.replace(".log", "")

        # Split by underscores
        parts = name.split("_")

        if len(parts) >= 5 and parts[0] == "task":
            task_id = int(parts[1])

            # Find timestamp part (YYYYMMDD format)
            timestamp_idx = None
            for i, part in enumerate(parts[2:], 2):
                if len(part) == 8 and part.isdigit():
                    timestamp_idx = i
                    break

            if timestamp_idx is not None and timestamp_idx + 1 < len(parts):
                # Directory context is everything between task_id and timestamp
                dir_context = "_".join(parts[2:timestamp_idx])
                timestamp = parts[timestamp_idx] + "_" + parts[timestamp_idx + 1]
                log_type = "_".join(parts[timestamp_idx + 2 :])

                return task_id, dir_context, timestamp, log_type

    except (ValueError, IndexError):
        pass

    return None


def get_safe_log_directory(base_dir: Optional[Path] = None) -> Path:
    """
    Get a safe logging directory, creating it if necessary.
    Cross-platform compatible.

    Args:
        base_dir: Optional base directory (defaults to ~/.claude-cto)

    Returns:
        Path to logs directory
    """
    if base_dir is None:
        # platform-specific directory resolution: Windows LOCALAPPDATA vs Unix home directory
        import os

        if os.name == "nt":  # Windows
            # Try to use LOCALAPPDATA first, then home
            app_data = os.environ.get("LOCALAPPDATA")
            if app_data:
                base_dir = Path(app_data) / "claude-cto"
            else:
                base_dir = Path.home() / ".claude-cto"
        else:
            # Unix-like systems
            base_dir = Path.home() / ".claude-cto"

    log_dir = base_dir / "tasks"

    # Create directory with proper permissions
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # Fall back to temp directory if can't create in preferred location
        import tempfile

        fallback_dir = Path(tempfile.gettempdir()) / "claude-cto" / "tasks"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir

    return log_dir


def cleanup_old_logs(log_dir: Path, max_age_days: int = 30, max_files: int = 1000):
    """
    Clean up old log files to prevent disk space issues.

    Args:
        log_dir: Directory containing log files
        max_age_days: Maximum age of log files to keep
        max_files: Maximum number of log files to keep (newest first)
    """
    try:
        log_files = list(log_dir.glob("task_*.log"))

        # Sort by modification time (newest first)
        log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        # Remove files beyond max_files limit
        if len(log_files) > max_files:
            for old_file in log_files[max_files:]:
                old_file.unlink()

        # Remove files older than max_age_days
        import time

        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)

        for log_file in log_files[:max_files]:  # Only check the files we're keeping
            if log_file.stat().st_mtime < cutoff_time:
                log_file.unlink()

    except Exception as e:
        # Don't fail the application if cleanup fails
        import logging

        logging.getLogger(__name__).warning(f"Log cleanup failed: {e}")


# Utility function for testing
def test_filename_generation():
    """Test filename generation with various edge cases."""
    test_cases = [
        "/home/user/my-project",
        "C:\\Users\\Dev\\My Project!",
        "/tmp/test",
        "/Users/jane/Documents/Web App #2",
        "\\\\server\\share\\project",
        "/very/long/path/with/many/directories/that/could/cause/issues",
        "C:\\Program Files (x86)\\My App\\config",
        "/home/user/项目/中文",
        "",
        ".",
    ]

    for i, directory in enumerate(test_cases, 1):
        filename = generate_log_filename(i, directory, "summary")
        print(f"Directory: {directory!r}")
        print(f"Filename:  {filename}")
        print(f"Parsed:    {parse_log_filename(filename)}")
        print("-" * 50)


if __name__ == "__main__":
    test_filename_generation()
