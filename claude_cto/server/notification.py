"""
SOLE RESPONSIBILITY: Cross-platform sound notification service for task completion events.
Provides non-blocking sound playback with fallback support for various platforms.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor

from .subprocess_manager import get_subprocess_manager

logger = logging.getLogger(__name__)

# Offload blocking sound playback to a separate thread pool
sound_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="sound")


class SoundNotifier:
    """Cross-platform sound notification system for task completion events."""

    def __init__(self):
        self.enabled = self._get_sound_enabled()
        self.start_sound = self._get_start_sound_path()
        self.success_sound = self._get_success_sound_path()
        self.failure_sound = self._get_failure_sound_path()
        self.sound_command = self._detect_sound_command()

        if self.enabled:
            logger.info(f"Sound notifications enabled using: {self.sound_command}")

    def _get_sound_enabled(self) -> bool:
        """Check if sound notifications are enabled via environment variable."""
        env_value = os.getenv("CLAUDE_CTO_ENABLE_SOUNDS", "true").lower()
        return env_value in ("true", "1", "yes", "on")

    def _get_start_sound_path(self) -> Optional[str]:
        """Get task start sound file path from environment or system defaults."""
        # Check environment variable first
        env_sound = os.getenv("CLAUDE_CTO_START_SOUND")
        if env_sound and Path(env_sound).exists():
            return env_sound

        # Check custom sounds directory
        custom_sound = Path.home() / ".claude-cto" / "sounds" / "start.wav"
        if custom_sound.exists():
            return str(custom_sound)

        # Try system default sounds
        system_sounds = [
            "/System/Library/Sounds/Ping.aiff",  # macOS - subtle start sound
            "/usr/share/sounds/alsa/Front_Right.wav",  # Linux ALSA
            "/usr/share/sounds/ubuntu/stereo/service-login.ogg",  # Ubuntu
        ]

        for sound in system_sounds:
            if Path(sound).exists():
                return sound

        return None

    def _get_success_sound_path(self) -> Optional[str]:
        """Get success sound file path from environment or system defaults."""
        # sound path resolution priority: environment variables > custom directory > system defaults
        env_sound = os.getenv("CLAUDE_CTO_SUCCESS_SOUND")
        if env_sound and Path(env_sound).exists():
            return env_sound

        # Check custom sounds directory
        custom_sound = Path.home() / ".claude-cto" / "sounds" / "success.wav"
        if custom_sound.exists():
            return str(custom_sound)

        # Try system default sounds
        system_sounds = [
            "/System/Library/Sounds/Glass.aiff",  # macOS
            "/usr/share/sounds/alsa/Front_Left.wav",  # Linux ALSA
            "/usr/share/sounds/ubuntu/stereo/desktop-login.ogg",  # Ubuntu
            # Windows fallback
            "C:\\Windows\\Media\\chimes.wav",  # Windows
        ]

        for sound in system_sounds:
            if Path(sound).exists():
                return sound

        return None

    def _get_failure_sound_path(self) -> Optional[str]:
        """Get failure sound file path from environment or system defaults."""
        # Check environment variable first
        env_sound = os.getenv("CLAUDE_CTO_FAILURE_SOUND")
        if env_sound and Path(env_sound).exists():
            return env_sound

        # Check custom sounds directory
        custom_sound = Path.home() / ".claude-cto" / "sounds" / "failure.wav"
        if custom_sound.exists():
            return str(custom_sound)

        # Try system default sounds
        system_sounds = [
            "/System/Library/Sounds/Basso.aiff",  # macOS
            "/usr/share/sounds/alsa/Side_Left.wav",  # Linux ALSA
            "/usr/share/sounds/ubuntu/stereo/system-error.ogg",  # Ubuntu
            # Windows fallback
            "C:\\Windows\\Media\\chord.wav",  # Windows error sound
        ]

        for sound in system_sounds:
            if Path(sound).exists():
                return sound

        return None

    def _detect_sound_command(self) -> Optional[str]:
        """Detect available sound playback command for the platform."""
        # OS-specific command priority: Windows PowerShell > macOS afplay > Linux paplay, with universal fallbacks
        if sys.platform == "win32":
            # Windows-specific commands
            commands = ["powershell", "mpv", "ffplay"]
        elif sys.platform == "darwin":
            # macOS-specific commands
            commands = ["afplay", "mpv", "ffplay"]
        else:
            # Linux/WSL commands
            commands = ["paplay", "aplay", "mpv", "ffplay"]

        for cmd in commands:
            if self._command_exists(cmd):
                return cmd

        return None

    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in the system PATH."""
        manager = get_subprocess_manager()
        return manager.check_command_exists(command)

    def _play_sound_sync(self, sound_path: str) -> bool:
        """
        Play sound synchronously in background thread.
        Returns True if successful, False otherwise.
        """
        if not self.sound_command or not sound_path:
            return False

        try:
            # command arguments tailored for each player: afplay direct vs mpv --no-video vs PowerShell .NET SoundPlayer
            if self.sound_command == "afplay":
                cmd = [self.sound_command, sound_path]
            elif self.sound_command in ["paplay", "aplay"]:
                cmd = [self.sound_command, sound_path]
            elif self.sound_command == "mpv":
                cmd = [self.sound_command, "--no-video", "--really-quiet", sound_path]
            elif self.sound_command == "ffplay":
                cmd = [
                    self.sound_command,
                    "-nodisp",
                    "-autoexit",
                    "-loglevel",
                    "quiet",
                    sound_path,
                ]
            elif self.sound_command == "powershell":
                # Windows PowerShell sound playback
                ps_script = f'(New-Object Media.SoundPlayer "{sound_path}").PlaySync()'
                cmd = [self.sound_command, "-Command", ps_script]
            else:
                cmd = [self.sound_command, sound_path]

            # Execute with timeout using subprocess manager
            manager = get_subprocess_manager()
            rc, stdout, stderr = manager.run_command(
                cmd,
                timeout=5,  # 5 second timeout for sound playback
                description=f"Playing sound: {Path(sound_path).name}",
            )

            if rc == 0:
                logger.debug(f"Sound played successfully: {sound_path}")
                return True
            else:
                logger.warning(f"Sound playback failed: {stderr}")
                return False

        except Exception as e:
            logger.warning(f"Error playing sound {sound_path}: {e}")
            return False

    async def play_start_sound(self) -> None:
        """Play task start sound asynchronously (non-blocking)."""
        if not self.enabled or not self.start_sound:
            return

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(sound_executor, self._play_sound_sync, self.start_sound)
        except Exception as e:
            logger.warning(f"Failed to play start sound: {e}")

    async def play_success_sound(self) -> None:
        """Play success sound asynchronously (non-blocking)."""
        if not self.enabled or not self.success_sound:
            return

        try:
            # background thread execution with async wrapper: prevents blocking the main event loop during sound playback
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(sound_executor, self._play_sound_sync, self.success_sound)
        except Exception as e:
            logger.warning(f"Failed to play success sound: {e}")

    async def play_failure_sound(self) -> None:
        """Play failure sound asynchronously (non-blocking)."""
        if not self.enabled or not self.failure_sound:
            return

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(sound_executor, self._play_sound_sync, self.failure_sound)
        except Exception as e:
            logger.warning(f"Failed to play failure sound: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get current notification configuration status."""
        return {
            "enabled": self.enabled,
            "sound_command": self.sound_command,
            "start_sound": self.start_sound,
            "success_sound": self.success_sound,
            "failure_sound": self.failure_sound,
            "supported": self.sound_command is not None,
        }


# Global notifier instance
_notifier = None


def get_notifier() -> SoundNotifier:
    """Get the global sound notifier instance (singleton pattern)."""
    global _notifier
    if _notifier is None:
        _notifier = SoundNotifier()
    return _notifier


async def notify_task_started(task_id: int) -> None:
    """
    Notify about task start with sound.

    Args:
        task_id: ID of the started task
    """
    notifier = get_notifier()
    logger.info(f"Task {task_id} started - playing start sound")
    await notifier.play_start_sound()


async def notify_task_completed(task_id: int, success: bool = True) -> None:
    """
    Notify about task completion with appropriate sound.

    Args:
        task_id: ID of the completed task
        success: True for successful completion, False for failure
    """
    notifier = get_notifier()

    if success:
        logger.info(f"Task {task_id} completed successfully - playing success sound")
        await notifier.play_success_sound()
    else:
        logger.info(f"Task {task_id} failed - playing failure sound")
        await notifier.play_failure_sound()


def configure_sounds(
    enable: Optional[bool] = None,
    start_sound: Optional[str] = None,
    success_sound: Optional[str] = None,
    failure_sound: Optional[str] = None,
) -> None:
    """
    Configure sound notifications programmatically.

    Args:
        enable: Enable or disable sound notifications
        start_sound: Path to start sound file
        success_sound: Path to success sound file
        failure_sound: Path to failure sound file
    """
    global _notifier

    if enable is not None:
        os.environ["CLAUDE_CTO_ENABLE_SOUNDS"] = "true" if enable else "false"

    if start_sound is not None:
        os.environ["CLAUDE_CTO_START_SOUND"] = start_sound

    if success_sound is not None:
        os.environ["CLAUDE_CTO_SUCCESS_SOUND"] = success_sound

    if failure_sound is not None:
        os.environ["CLAUDE_CTO_FAILURE_SOUND"] = failure_sound

    # Reinitialize notifier with new settings
    _notifier = None
