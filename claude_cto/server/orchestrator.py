"""
SOLE RESPONSIBILITY: Manages the execution of task DAGs with dependency resolution
and delay management. Validates graphs, detects cycles, and coordinates task execution.
"""

import asyncio
import json
from typing import Dict, List
from . import models, crud
from .executor import TaskExecutor
from .database import get_session


class CycleDetectedError(Exception):
    """Raised when a circular dependency is detected in the task graph."""

    pass


class InvalidDependencyError(Exception):
    """Raised when a task depends on a non-existent identifier."""

    pass


class TaskOrchestrator:
    """
    Coordinates the execution of multiple tasks with dependencies.
    Manages task lifecycle, dependency resolution, and failure propagation.
    """

    def __init__(self, orchestration_id: int):
        self.orchestration_id = orchestration_id
        self.task_map: Dict[str, int] = {}  # identifier -> task_id
        self.dependency_graph: Dict[str, List[str]] = {}  # identifier -> [dependencies]
        self.task_events: Dict[str, asyncio.Event] = {}  # identifier -> completion event
        self.task_statuses: Dict[str, models.TaskStatus] = {}  # identifier -> status
        self._lock = asyncio.Lock()  # For thread-safe status updates

    async def run(self) -> None:
        """Main orchestration loop."""
        # Load orchestration and tasks from database
        await self._load_orchestration()

        # Validate the dependency graph
        self._validate_graph()

        # Create asyncio events for each task
        for identifier in self.task_map:
            self.task_events[identifier] = asyncio.Event()
            self.task_statuses[identifier] = models.TaskStatus.WAITING

        # Update orchestration status to running
        await self._update_orchestration_status("running")

        # Start all tasks concurrently
        tasks = []
        for identifier in self.task_map:
            task = asyncio.create_task(self._run_task(identifier))
            tasks.append(task)

        # Wait for all tasks to complete or fail
        await asyncio.gather(*tasks, return_exceptions=True)

        # Finalize orchestration
        await self._finalize_orchestration()

    async def _load_orchestration(self) -> None:
        """Load orchestration and tasks from database."""
        for session in get_session():
            # Use CRUD layer to get tasks - maintains SOLE principle
            tasks = crud.get_tasks_by_orchestration(session, self.orchestration_id)

            for task in tasks:
                # Store the mapping
                identifier = task.identifier
                if identifier:
                    self.task_map[identifier] = task.id

                    # Parse dependencies
                    if task.depends_on:
                        deps = json.loads(task.depends_on)
                        self.dependency_graph[identifier] = deps
                    else:
                        self.dependency_graph[identifier] = []

    def _validate_graph(self) -> None:
        """Validate the dependency graph for cycles and invalid references."""
        # Check for invalid dependencies
        all_identifiers = set(self.task_map.keys())
        for identifier, deps in self.dependency_graph.items():
            for dep in deps:
                if dep not in all_identifiers:
                    raise InvalidDependencyError(f"Task '{identifier}' depends on non-existent task '{dep}'")

        # Check for cycles using DFS
        visited = set()
        rec_stack = set()

        def has_cycle(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in self.dependency_graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in self.task_map:
            if node not in visited:
                if has_cycle(node):
                    raise CycleDetectedError(f"Circular dependency detected involving task '{node}'")

    async def _run_task(self, identifier: str) -> None:
        """Run a single task with dependency and delay management."""
        task_id = self.task_map[identifier]

        try:
            # Wait for dependencies
            deps = self.dependency_graph.get(identifier, [])
            if deps:
                await self._wait_for_dependencies(identifier, deps)

            # Check if any dependency failed
            if await self._any_dependency_failed(deps):
                await self._mark_task_skipped(task_id, identifier)
                return

            # Apply initial delay if specified
            for session in get_session():
                task = session.get(models.TaskDB, task_id)
                if task and task.initial_delay:
                    await asyncio.sleep(task.initial_delay)

            # Update status to pending (ready to run)
            await self._update_task_status(task_id, identifier, models.TaskStatus.PENDING)

            # Execute the task
            executor = TaskExecutor(task_id)
            await executor.run()

            # Get final status
            for session in get_session():
                task = session.get(models.TaskDB, task_id)
                if task:
                    async with self._lock:
                        self.task_statuses[identifier] = task.status
                        self.task_events[identifier].set()

        except Exception as e:
            # Mark task as failed and signal completion
            await self._mark_task_failed(task_id, identifier, str(e))

    async def _wait_for_dependencies(self, identifier: str, deps: List[str]) -> None:
        """Wait for all dependencies to complete."""
        wait_tasks = []
        for dep in deps:
            if dep in self.task_events:
                wait_tasks.append(self.task_events[dep].wait())

        if wait_tasks:
            await asyncio.gather(*wait_tasks)

    async def _any_dependency_failed(self, deps: List[str]) -> bool:
        """Check if any dependency failed."""
        async with self._lock:
            for dep in deps:
                status = self.task_statuses.get(dep)
                if status in [models.TaskStatus.FAILED, models.TaskStatus.SKIPPED]:
                    return True
        return False

    async def _mark_task_skipped(self, task_id: int, identifier: str) -> None:
        """Mark a task as skipped due to dependency failure."""
        for session in get_session():
            # Use CRUD layer - maintains SOLE principle
            crud.mark_task_skipped(session, task_id)

        async with self._lock:
            self.task_statuses[identifier] = models.TaskStatus.SKIPPED
            self.task_events[identifier].set()

    async def _mark_task_failed(self, task_id: int, identifier: str, error: str) -> None:
        """Mark a task as failed."""
        for session in get_session():
            # Use CRUD layer - maintains SOLE principle
            crud.mark_task_failed(session, task_id, error)

        async with self._lock:
            self.task_statuses[identifier] = models.TaskStatus.FAILED
            self.task_events[identifier].set()

    async def _update_task_status(self, task_id: int, identifier: str, status: models.TaskStatus) -> None:
        """Update task status in database and memory."""
        for session in get_session():
            # Use CRUD layer - maintains SOLE principle
            crud.update_task_status(session, task_id, status)

        async with self._lock:
            self.task_statuses[identifier] = status

    async def _update_orchestration_status(self, status: str) -> None:
        """Update orchestration status in database."""
        for session in get_session():
            # Use CRUD layer - maintains SOLE principle
            crud.update_orchestration_status(session, self.orchestration_id, status)

    async def _finalize_orchestration(self) -> None:
        """Finalize the orchestration with summary statistics."""
        completed = 0
        failed = 0
        skipped = 0

        async with self._lock:
            for status in self.task_statuses.values():
                if status == models.TaskStatus.COMPLETED:
                    completed += 1
                elif status == models.TaskStatus.FAILED:
                    failed += 1
                elif status == models.TaskStatus.SKIPPED:
                    skipped += 1

        final_status = "completed" if failed == 0 else "failed"

        for session in get_session():
            # Use CRUD layer - maintains SOLE principle
            crud.update_orchestration_status(
                session,
                self.orchestration_id,
                final_status,
                completed_tasks=completed,
                failed_tasks=failed,
                skipped_tasks=skipped,
            )
