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
    """
    Individual task performance metrics: tracks resource consumption throughout task lifecycle.
    Critical for identifying resource-intensive tasks and optimizing system performance.
    """

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
        """
        Task duration calculation: provides execution time for performance analysis.
        Returns None for active tasks, seconds for completed tasks.
        """
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None  # Task still running

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialization for logging and monitoring: converts metrics to JSON-compatible format.
        Used by monitoring dashboards, alerting systems, and performance analysis tools.
        """
        return {
            "task_id": self.task_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "peak_memory_mb": round(self.peak_memory_mb, 2),  # Rounded for readability
            "avg_memory_mb": round(self.avg_memory_mb, 2),
            "cpu_percent": round(self.cpu_percent, 2),
            "io_reads": self.io_reads,
            "io_writes": self.io_writes,
            "error_count": self.error_count,
            "retry_count": self.retry_count,
            "messages_processed": self.messages_processed,  # AI conversation turns
        }


@dataclass
class SystemMetrics:
    """
    System-wide performance metrics: captures server health and resource utilization.
    Essential for capacity planning, alerting, and identifying system bottlenecks.
    """

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
    """
    Comprehensive resource monitoring system: tracks memory, CPU, and I/O for tasks and system.
    
    CRITICAL LIFECYCLE REQUIREMENTS:
    1. MUST call start_global_monitoring() during server startup
    2. MUST call stop_global_monitoring() during server shutdown
    3. MUST call cleanup_old_metrics() periodically to prevent memory leaks
    
    Failure to follow lifecycle requirements results in:
    - Non-functional monitoring (missing start_global_monitoring)
    - Resource exhaustion (missing cleanup_old_metrics)
    - Hung background tasks (missing stop_global_monitoring)
    """

    def __init__(self, check_interval: float = 5.0):
        """
        Monitor initialization: establishes monitoring infrastructure without starting background tasks.
        Lightweight constructor - actual monitoring begins when start_monitoring() is called.

        CRITICAL: This constructor only prepares monitoring - you MUST call lifecycle methods:
        1. start_global_monitoring() - begins background monitoring loop
        2. stop_global_monitoring() - stops monitoring and cleans up tasks
        3. cleanup_old_metrics() - prevents memory accumulation (auto-called by monitoring loop)

        Args:
            check_interval: Seconds between monitoring cycles (affects monitoring granularity)
        """
        # Monitoring configuration: determines sampling rate and data collection frequency
        self.check_interval = check_interval
        # Task metrics storage: accumulates performance data for all tasks (MUST be cleaned up)
        self.task_metrics: Dict[int, TaskMetrics] = {}
        # System metrics history: rolling window of system performance (auto-cleaned hourly)
        self.system_metrics_history: List[SystemMetrics] = []
        # Monitoring state control: prevents duplicate monitoring loops
        self.monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None  # Background monitoring task

        # Alerting thresholds: configurable limits for system resource warnings
        self.memory_warning_threshold = 80.0   # Warning level - log alerts
        self.memory_critical_threshold = 95.0  # Critical level - may trigger cleanup

        # Process tracking: monitors current server process for resource usage
        self.process = psutil.Process(os.getpid())

    def start_task_monitoring(self, task_id: int) -> TaskMetrics:
        """
        Task monitoring initiation: begins tracking resource consumption for specific task.
        Called by TaskExecutor when task execution starts - establishes baseline metrics.
        """
        # Metrics object creation: initializes performance tracking for task lifecycle
        metrics = TaskMetrics(task_id=task_id, start_time=datetime.now())
        self.task_metrics[task_id] = metrics  # Register in monitoring system
        logger.info(f"Started monitoring task {task_id}")
        return metrics  # Return metrics object for potential direct updates

    def end_task_monitoring(self, task_id: int, success: bool = True) -> Optional[TaskMetrics]:
        """
        Task monitoring completion: finalizes resource tracking and records final metrics.
        Called by TaskExecutor when task completes (success or failure) - calculates final statistics.
        """
        # Metrics validation: ensures task was being monitored
        if task_id not in self.task_metrics:
            return None  # Task not being monitored - silent failure

        # Task completion processing: finalize metrics and record end state
        metrics = self.task_metrics[task_id]
        metrics.end_time = datetime.now()  # Completion timestamp for duration calculation

        # Error tracking: increments failure count for system reliability metrics
        if not success:
            metrics.error_count += 1

        # Completion logging: records final task performance data
        logger.info(f"Ended monitoring task {task_id}: {metrics.to_dict()}")
        return metrics  # Return final metrics for logging or analysis

    def update_task_metrics(
        self,
        task_id: int,
        messages: Optional[int] = None,
        errors: Optional[int] = None,
        retries: Optional[int] = None,
    ) -> None:
        """
        Real-time task metrics update: allows TaskExecutor to report progress during execution.
        Enables monitoring of AI conversation progress, error accumulation, and retry patterns.
        """
        # Task existence validation: silently ignores updates for non-monitored tasks
        if task_id not in self.task_metrics:
            return  # Task not being monitored - skip update

        # Metrics update: selectively updates provided parameters
        metrics = self.task_metrics[task_id]

        # Progress indicators: tracks AI conversation turns and system interactions
        if messages is not None:
            metrics.messages_processed = messages  # Claude SDK message count
        if errors is not None:
            metrics.error_count = errors  # Accumulated error count
        if retries is not None:
            metrics.retry_count = retries  # Retry attempt count

    async def start_monitoring(self) -> None:
        """
        Background monitoring initiation: starts continuous system and task resource tracking.
        Creates asyncio task for monitoring loop - CRITICAL for system health visibility.
        """
        # Duplicate monitoring prevention: ensures only one monitoring loop per instance
        if self.monitoring:
            return  # Already monitoring - avoid duplicate background tasks

        # Monitoring activation: starts background data collection
        self.monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())  # Background monitoring task
        logger.info("Started memory monitoring")

    async def stop_monitoring(self) -> None:
        """
        Background monitoring shutdown: cleanly stops monitoring loop and cancels background task.
        CRITICAL for server shutdown - prevents hung tasks and resource leaks.
        """
        # Monitoring deactivation: signals monitoring loop to exit
        self.monitoring = False

        # Background task cleanup: cancels monitoring loop and waits for completion
        if self._monitor_task:
            self._monitor_task.cancel()  # Signal cancellation to monitoring loop
            try:
                await self._monitor_task  # Wait for graceful shutdown
            except asyncio.CancelledError:
                pass  # Expected exception from cancellation - safe to ignore
            self._monitor_task = None  # Clear task reference

        logger.info("Stopped memory monitoring")

    async def _monitor_loop(self) -> None:
        """
        Core monitoring loop: continuous data collection, analysis, and cleanup cycle.
        Runs in background until monitoring is disabled - handles all system monitoring functions.
        CRITICAL: Includes automatic cleanup to prevent memory leaks in long-running servers.
        """
        while self.monitoring:  # Continue until monitoring is disabled
            try:
                # System metrics collection: gathers current resource usage statistics
                metrics = self._collect_system_metrics()
                self.system_metrics_history.append(metrics)  # Add to historical data

                # Active task monitoring: updates resource usage for running tasks
                self._update_active_task_metrics()

                # Threshold monitoring: checks for resource usage alerts
                self._check_memory_thresholds(metrics)

                # Historical data cleanup: maintains 1-hour rolling window to prevent memory growth
                cutoff = datetime.now() - timedelta(hours=1)
                self.system_metrics_history = [m for m in self.system_metrics_history if m.timestamp > cutoff]

                # Task metrics cleanup: prevents unbounded memory growth from completed tasks
                # Triggered when task count exceeds threshold - critical for long-running servers
                if len(self.task_metrics) > 100:
                    self.cleanup_old_metrics(older_than_hours=24)  # Remove 24+ hour old tasks

                # Monitoring interval: controls data collection frequency
                await asyncio.sleep(self.check_interval)

            except Exception as e:
                # Error resilience: continues monitoring despite individual collection failures
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)  # Wait before retry

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
            active_tasks = sum(1 for m in self.task_metrics.values() if m.end_time is None)

            # Calculate 1-hour stats
            one_hour_ago = datetime.now() - timedelta(hours=1)
            recent_tasks = [m for m in self.task_metrics.values() if m.start_time > one_hour_ago]

            failed_tasks_1h = sum(1 for m in recent_tasks if m.error_count > 0)
            completed_tasks_1h = sum(1 for m in recent_tasks if m.end_time is not None)

            success_rate_1h = 0.0
            if completed_tasks_1h > 0:
                success_rate_1h = (completed_tasks_1h - failed_tasks_1h) / completed_tasks_1h * 100

            # Average duration
            durations = [m.duration_seconds for m in recent_tasks if m.duration_seconds is not None]
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
                    metrics.peak_memory_mb = max(metrics.peak_memory_mb, current_memory_mb)

                    # Update average memory (simple moving average)
                    if metrics.avg_memory_mb == 0:
                        metrics.avg_memory_mb = current_memory_mb
                    else:
                        metrics.avg_memory_mb = (metrics.avg_memory_mb + current_memory_mb) / 2

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
                f"CRITICAL: Memory usage at {metrics.memory_percent:.1f}% " f"({metrics.memory_used_mb:.0f}MB used)"
            )
            # Could trigger cleanup or task cancellation here

        elif metrics.memory_percent >= self.memory_warning_threshold:
            logger.warning(
                f"WARNING: Memory usage at {metrics.memory_percent:.1f}% " f"({metrics.memory_used_mb:.0f}MB used)"
            )

    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current system and task metrics."""
        current_system = self._collect_system_metrics()

        return {
            "system": current_system.to_dict(),
            "active_tasks": [m.to_dict() for m in self.task_metrics.values() if m.end_time is None],
            "recent_completed": [m.to_dict() for m in self.task_metrics.values() if m.end_time is not None][
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
        """
        Critical memory leak prevention: removes old completed task metrics from memory.
        MUST be called periodically (auto-called by monitoring loop) to prevent memory exhaustion.
        Targets completed tasks only - preserves active task monitoring data.
        """
        # Cleanup threshold: defines age limit for task metrics retention
        cutoff = datetime.now() - timedelta(hours=older_than_hours)
        
        # Old task identification: finds completed tasks older than threshold
        old_tasks = [
            task_id
            for task_id, metrics in self.task_metrics.items()
            # Only remove completed tasks (end_time is not None) older than cutoff
            if metrics.start_time < cutoff and metrics.end_time is not None
        ]

        # Memory cleanup: removes old task metrics from tracking dictionary
        for task_id in old_tasks:
            del self.task_metrics[task_id]  # Free memory by removing metrics object

        # Cleanup logging: reports memory reclamation for monitoring
        if old_tasks:
            logger.info(f"Cleaned up {len(old_tasks)} old task metrics")

        return len(old_tasks)  # Return count for monitoring and testing


# Global singleton instance for the monitor
_monitor = None


def get_memory_monitor() -> MemoryMonitor:
    """
    Global monitor singleton: provides system-wide access to memory monitoring instance.
    Lazy initialization ensures single monitor instance across entire server process.
    """
    # Lazily initialize the singleton on first request
    global _monitor
    if _monitor is None:
        _monitor = MemoryMonitor()  # Lazy initialization on first access
    return _monitor


async def start_global_monitoring() -> None:
    """
    Global monitoring activation: starts system-wide resource tracking for server lifecycle.
    MUST be called during server startup to enable monitoring functionality.
    """
    monitor = get_memory_monitor()  # Get singleton instance
    await monitor.start_monitoring()  # Begin background monitoring loop


async def stop_global_monitoring() -> None:
    """
    Global monitoring shutdown: cleanly stops system-wide resource tracking during server shutdown.
    MUST be called during server shutdown to prevent hung background tasks.
    """
    monitor = get_memory_monitor()  # Get singleton instance
    await monitor.stop_monitoring()  # Stop background monitoring loop
