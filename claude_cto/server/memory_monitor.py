"""
SOLE RESPONSIBILITY: Memory and resource monitoring for claude-cto.
Tracks memory usage, task performance metrics, and system health.
"""

import os
import psutil
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class TaskMetrics:
    """Metrics for a single task execution."""

    task_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    peak_memory_mb: float = 0.0
    avg_memory_mb: float = 0.0
    cpu_percent: float = 0.0
    io_reads: int = 0
    io_writes: int = 0
    error_count: int = 0
    retry_count: int = 0
    messages_processed: int = 0

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get task duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            "task_id": self.task_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "peak_memory_mb": round(self.peak_memory_mb, 2),
            "avg_memory_mb": round(self.avg_memory_mb, 2),
            "cpu_percent": round(self.cpu_percent, 2),
            "io_reads": self.io_reads,
            "io_writes": self.io_writes,
            "error_count": self.error_count,
            "retry_count": self.retry_count,
            "messages_processed": self.messages_processed,
        }


@dataclass
class SystemMetrics:
    """System-wide metrics."""

    timestamp: datetime = field(default_factory=datetime.now)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_available_mb: float = 0.0
    disk_usage_percent: float = 0.0
    active_tasks: int = 0
    pending_tasks: int = 0
    failed_tasks_1h: int = 0
    success_rate_1h: float = 0.0
    avg_task_duration_1h: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu_percent": round(self.cpu_percent, 2),
            "memory_percent": round(self.memory_percent, 2),
            "memory_used_mb": round(self.memory_used_mb, 2),
            "memory_available_mb": round(self.memory_available_mb, 2),
            "disk_usage_percent": round(self.disk_usage_percent, 2),
            "active_tasks": self.active_tasks,
            "pending_tasks": self.pending_tasks,
            "failed_tasks_1h": self.failed_tasks_1h,
            "success_rate_1h": round(self.success_rate_1h, 2),
            "avg_task_duration_1h": round(self.avg_task_duration_1h, 2),
        }


class MemoryMonitor:
    """Monitor memory and resource usage for tasks and system.
    
    ⚠️ WARNING: This monitor MUST be started with start_global_monitoring() in the
    server lifespan context or memory tracking will be non-functional. The monitor
    also MUST call cleanup_old_metrics() periodically to prevent unbounded memory growth.
    """

    def __init__(self, check_interval: float = 5.0):
        """
        Initialize memory monitor.
        
        ⚠️ CRITICAL: After initialization, you MUST:
        1. Call start_global_monitoring() to begin tracking
        2. Call stop_global_monitoring() on shutdown
        3. Call cleanup_old_metrics() periodically (handled by monitoring loop)

        Args:
            check_interval: Seconds between memory checks
        """
        self.check_interval = check_interval
        self.task_metrics: Dict[int, TaskMetrics] = {}
        self.system_metrics_history: List[SystemMetrics] = []
        self.monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None

        # Memory thresholds for alerting
        self.memory_warning_threshold = 80.0  # percent
        self.memory_critical_threshold = 95.0  # percent

        # Track process
        self.process = psutil.Process(os.getpid())

    def start_task_monitoring(self, task_id: int) -> TaskMetrics:
        """Start monitoring a task."""
        metrics = TaskMetrics(task_id=task_id, start_time=datetime.now())
        self.task_metrics[task_id] = metrics
        logger.info(f"Started monitoring task {task_id}")
        return metrics

    def end_task_monitoring(
        self, task_id: int, success: bool = True
    ) -> Optional[TaskMetrics]:
        """End monitoring a task."""
        if task_id not in self.task_metrics:
            return None

        metrics = self.task_metrics[task_id]
        metrics.end_time = datetime.now()

        if not success:
            metrics.error_count += 1

        logger.info(f"Ended monitoring task {task_id}: {metrics.to_dict()}")
        return metrics

    def update_task_metrics(
        self,
        task_id: int,
        messages: Optional[int] = None,
        errors: Optional[int] = None,
        retries: Optional[int] = None,
    ) -> None:
        """Update task metrics during execution."""
        if task_id not in self.task_metrics:
            return

        metrics = self.task_metrics[task_id]

        if messages is not None:
            metrics.messages_processed = messages
        if errors is not None:
            metrics.error_count = errors
        if retries is not None:
            metrics.retry_count = retries

    async def start_monitoring(self) -> None:
        """Start the background monitoring loop."""
        if self.monitoring:
            return

        self.monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Started memory monitoring")

    async def stop_monitoring(self) -> None:
        """Stop the background monitoring loop."""
        self.monitoring = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

        logger.info("Stopped memory monitoring")

    async def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self.monitoring:
            try:
                # Collect metrics
                metrics = self._collect_system_metrics()
                self.system_metrics_history.append(metrics)

                # Update task metrics
                self._update_active_task_metrics()

                # Check thresholds
                self._check_memory_thresholds(metrics)

                # Cleanup old history (keep last hour)
                cutoff = datetime.now() - timedelta(hours=1)
                self.system_metrics_history = [
                    m for m in self.system_metrics_history if m.timestamp > cutoff
                ]

                # Cleanup old task metrics periodically (every 10 iterations)
                if len(self.task_metrics) > 100:
                    self.cleanup_old_metrics(older_than_hours=24)

                # Wait for next check
                await asyncio.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)

    def _collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_mb = memory.used / (1024 * 1024)
            memory_available_mb = memory.available / (1024 * 1024)

            # Disk usage
            disk = psutil.disk_usage("/")
            disk_usage_percent = disk.percent

            # Task counts
            active_tasks = sum(
                1 for m in self.task_metrics.values() if m.end_time is None
            )

            # Calculate 1-hour stats
            one_hour_ago = datetime.now() - timedelta(hours=1)
            recent_tasks = [
                m for m in self.task_metrics.values() if m.start_time > one_hour_ago
            ]

            failed_tasks_1h = sum(1 for m in recent_tasks if m.error_count > 0)
            completed_tasks_1h = sum(1 for m in recent_tasks if m.end_time is not None)

            success_rate_1h = 0.0
            if completed_tasks_1h > 0:
                success_rate_1h = (
                    (completed_tasks_1h - failed_tasks_1h) / completed_tasks_1h * 100
                )

            # Average duration
            durations = [
                m.duration_seconds
                for m in recent_tasks
                if m.duration_seconds is not None
            ]
            avg_task_duration_1h = sum(durations) / len(durations) if durations else 0.0

            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_mb=memory_used_mb,
                memory_available_mb=memory_available_mb,
                disk_usage_percent=disk_usage_percent,
                active_tasks=active_tasks,
                pending_tasks=0,  # TODO: Get from database
                failed_tasks_1h=failed_tasks_1h,
                success_rate_1h=success_rate_1h,
                avg_task_duration_1h=avg_task_duration_1h,
            )

        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return SystemMetrics()

    def _update_active_task_metrics(self) -> None:
        """Update metrics for active tasks."""
        try:
            # Get current process memory
            memory_info = self.process.memory_info()
            current_memory_mb = memory_info.rss / (1024 * 1024)

            # Get CPU usage
            cpu_percent = self.process.cpu_percent()

            # Get I/O stats (if available)
            try:
                io_counters = self.process.io_counters()
                io_reads = io_counters.read_count
                io_writes = io_counters.write_count
            except (AttributeError, psutil.AccessDenied):
                io_reads = 0
                io_writes = 0

            # Update active task metrics
            for task_id, metrics in self.task_metrics.items():
                if metrics.end_time is None:  # Still active
                    # Update peak memory
                    metrics.peak_memory_mb = max(
                        metrics.peak_memory_mb, current_memory_mb
                    )

                    # Update average memory (simple moving average)
                    if metrics.avg_memory_mb == 0:
                        metrics.avg_memory_mb = current_memory_mb
                    else:
                        metrics.avg_memory_mb = (
                            metrics.avg_memory_mb + current_memory_mb
                        ) / 2

                    # Update CPU
                    metrics.cpu_percent = cpu_percent

                    # Update I/O
                    metrics.io_reads = io_reads
                    metrics.io_writes = io_writes

        except Exception as e:
            logger.error(f"Error updating task metrics: {e}")

    def _check_memory_thresholds(self, metrics: SystemMetrics) -> None:
        """Check if memory usage exceeds thresholds."""
        if metrics.memory_percent >= self.memory_critical_threshold:
            logger.critical(
                f"CRITICAL: Memory usage at {metrics.memory_percent:.1f}% "
                f"({metrics.memory_used_mb:.0f}MB used)"
            )
            # Could trigger cleanup or task cancellation here

        elif metrics.memory_percent >= self.memory_warning_threshold:
            logger.warning(
                f"WARNING: Memory usage at {metrics.memory_percent:.1f}% "
                f"({metrics.memory_used_mb:.0f}MB used)"
            )

    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current system and task metrics."""
        current_system = self._collect_system_metrics()

        return {
            "system": current_system.to_dict(),
            "active_tasks": [
                m.to_dict() for m in self.task_metrics.values() if m.end_time is None
            ],
            "recent_completed": [
                m.to_dict()
                for m in self.task_metrics.values()
                if m.end_time is not None
            ][
                -10:
            ],  # Last 10 completed
            "thresholds": {
                "memory_warning": self.memory_warning_threshold,
                "memory_critical": self.memory_critical_threshold,
            },
        }

    def get_task_metrics(self, task_id: int) -> Optional[TaskMetrics]:
        """Get metrics for a specific task."""
        return self.task_metrics.get(task_id)

    def cleanup_old_metrics(self, older_than_hours: int = 24) -> int:
        """Clean up old task metrics to prevent memory leak."""
        cutoff = datetime.now() - timedelta(hours=older_than_hours)
        old_tasks = [
            task_id
            for task_id, metrics in self.task_metrics.items()
            if metrics.start_time < cutoff and metrics.end_time is not None
        ]

        for task_id in old_tasks:
            del self.task_metrics[task_id]

        if old_tasks:
            logger.info(f"Cleaned up {len(old_tasks)} old task metrics")

        return len(old_tasks)


# Global memory monitor instance
_monitor = None


def get_memory_monitor() -> MemoryMonitor:
    """Get the global memory monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = MemoryMonitor()
    return _monitor


async def start_global_monitoring() -> None:
    """Start global memory monitoring."""
    monitor = get_memory_monitor()
    await monitor.start_monitoring()


async def stop_global_monitoring() -> None:
    """Stop global memory monitoring."""
    monitor = get_memory_monitor()
    await monitor.stop_monitoring()
