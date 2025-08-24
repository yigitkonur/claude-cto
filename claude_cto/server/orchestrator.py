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
    """
    DAG validation error: raised when task dependencies form cycles.
    Critical for preventing infinite dependency loops and deadlocked orchestrations.
    """
    pass


class InvalidDependencyError(Exception):
    """
    Dependency validation error: raised when task references non-existent dependency.
    Prevents orchestration startup with broken dependency references.
    """
    pass


class TaskOrchestrator:
    """
    DAG execution engine: orchestrates dependent task execution with event-driven coordination.
    Critical for complex workflows - uses asyncio.Event for efficient dependency waiting.
    Validates graph structure, manages task lifecycle, and handles failure propagation.
    """

    def __init__(self, orchestration_id: int):
        # Orchestration identification: links to database orchestration record
        self.orchestration_id = orchestration_id
        # Task mapping: translates human-readable identifiers to database task IDs
        self.task_map: Dict[str, int] = {}  # identifier -> task_id
        # Dependency graph: represents task relationships as adjacency list
        self.dependency_graph: Dict[str, List[str]] = {}  # identifier -> [dependencies]
        # Event coordination: asyncio.Event objects for efficient dependency waiting
        # CRITICAL: prevents polling loops - tasks wait on events, not status checks
        self.task_events: Dict[str, asyncio.Event] = {}  # identifier -> completion event
        # Status tracking: maintains current state of all orchestrated tasks
        self.task_statuses: Dict[str, models.TaskStatus] = {}  # identifier -> status
        # Concurrency control: protects shared state from race conditions
        self._lock = asyncio.Lock()  # Thread-safe status updates

    async def run(self) -> None:
        """
        Main orchestration controller: manages complete DAG execution lifecycle.
        Phase 1: Load and validate → Phase 2: Execute → Phase 3: Finalize
        Critical for coordinating dependent tasks with proper error handling.
        """
        # Phase 1: Orchestration setup and validation
        await self._load_orchestration()  # Load tasks and dependencies from database
        self._validate_graph()  # Ensure DAG is valid (no cycles, valid references)

        # Event infrastructure setup: creates coordination objects for dependency waiting
        # CRITICAL: asyncio.Event enables efficient waiting without polling
        for identifier in self.task_map:
            self.task_events[identifier] = asyncio.Event()  # Completion signaling
            self.task_statuses[identifier] = models.TaskStatus.WAITING  # Initial state

        # Orchestration state transition: marks orchestration as actively running
        await self._update_orchestration_status("running")

        # Phase 2: Concurrent task execution with dependency coordination
        # All tasks start simultaneously but wait for dependencies via asyncio.Event
        tasks = []
        for identifier in self.task_map:
            task = asyncio.create_task(self._run_task(identifier))  # Background task execution
            tasks.append(task)

        # Task completion synchronization: waits for all tasks regardless of success/failure
        await asyncio.gather(*tasks, return_exceptions=True)  # Prevents early termination

        # Phase 3: Orchestration finalization with summary statistics
        await self._finalize_orchestration()

    async def _load_orchestration(self) -> None:
        """
        Orchestration data loading: retrieves tasks and dependencies from database.
        Builds in-memory graph representation for efficient dependency resolution.
        """
        for session in get_session():
            # Database query: loads all tasks belonging to this orchestration
            # CRUD layer usage maintains architectural SOLE principle
            tasks = crud.get_tasks_by_orchestration(session, self.orchestration_id)

            for task in tasks:
                # Task registration: builds identifier-to-ID mapping
                identifier = task.identifier
                if identifier:
                    self.task_map[identifier] = task.id  # Map human-readable name to DB ID

                    # Dependency parsing: converts JSON dependency list to graph structure
                    if task.depends_on:
                        deps = json.loads(task.depends_on)  # Parse JSON dependency array
                        self.dependency_graph[identifier] = deps
                    else:
                        self.dependency_graph[identifier] = []  # No dependencies

    def _validate_graph(self) -> None:
        """
        DAG validation: ensures dependency graph is valid and executable.
        Two-phase validation: reference checking → cycle detection
        CRITICAL: prevents deadlocked orchestrations and invalid dependency references.
        """
        # Phase 1: Dependency reference validation
        # Ensures all referenced dependencies exist in the orchestration
        all_identifiers = set(self.task_map.keys())
        for identifier, deps in self.dependency_graph.items():
            for dep in deps:
                if dep not in all_identifiers:
                    raise InvalidDependencyError(f"Task '{identifier}' depends on non-existent task '{dep}'")

        # Phase 2: Cycle detection using Depth-First Search (DFS)
        # Prevents infinite dependency loops that would deadlock orchestration
        visited = set()     # Tracks all visited nodes
        rec_stack = set()   # Tracks current recursion path

        def has_cycle(node: str) -> bool:
            """DFS cycle detection: identifies circular dependencies in graph"""
            visited.add(node)    # Mark node as visited
            rec_stack.add(node)  # Add to current path

            # Check all dependencies of current node
            for neighbor in self.dependency_graph.get(node, []):
                if neighbor not in visited:
                    # Recurse into unvisited dependency
                    if has_cycle(neighbor):
                        return True  # Cycle found in subtree
                elif neighbor in rec_stack:
                    # Back edge detected - cycle found
                    return True

            rec_stack.remove(node)  # Remove from current path
            return False  # No cycle found from this node

        # Validate all connected components in the graph
        for node in self.task_map:
            if node not in visited:
                if has_cycle(node):
                    raise CycleDetectedError(f"Circular dependency detected involving task '{node}'")

    async def _run_task(self, identifier: str) -> None:
        """
        Individual task execution: manages single task lifecycle within orchestration.
        Sequence: dependency wait → failure check → delay → execution → completion signaling
        Critical for proper task coordination and failure propagation.
        """
        task_id = self.task_map[identifier]

        try:
            # Dependency coordination: waits for prerequisite tasks using asyncio.Event
            # CRITICAL: uses event-driven waiting, not polling, for efficiency
            deps = self.dependency_graph.get(identifier, [])
            if deps:
                await self._wait_for_dependencies(identifier, deps)

            # Dependency failure propagation: skips task if any dependency failed
            if await self._any_dependency_failed(deps):
                await self._mark_task_skipped(task_id, identifier)
                return  # Early exit - task cannot execute

            # Execution delay: applies configured delay after dependencies complete
            # Useful for file system sync, API rate limiting, or staged deployments
            for session in get_session():
                task = session.get(models.TaskDB, task_id)
                if task and task.initial_delay:
                    await asyncio.sleep(task.initial_delay)  # Blocking delay

            # Task state transition: marks task as ready for execution
            await self._update_task_status(task_id, identifier, models.TaskStatus.PENDING)

            # Core task execution: delegates to TaskExecutor for actual work
            executor = TaskExecutor(task_id)
            await executor.run()  # Execute task with full SDK integration

            # Completion processing: reads final status and signals completion
            for session in get_session():
                task = session.get(models.TaskDB, task_id)
                if task:
                    # Thread-safe status update and event signaling
                    async with self._lock:
                        self.task_statuses[identifier] = task.status
                        self.task_events[identifier].set()  # Signal completion to waiting tasks

        except Exception as e:
            # Exception handling: marks task as failed and signals completion
            await self._mark_task_failed(task_id, identifier, str(e))

    async def _wait_for_dependencies(self, identifier: str, deps: List[str]) -> None:
        """
        Event-driven dependency waiting: efficiently waits for prerequisite task completion.
        CRITICAL: uses asyncio.Event.wait() instead of polling - scales efficiently with task count.
        Only proceeds when ALL dependencies have completed (success or failure).
        """
        # Event collection: gathers completion events for all dependencies
        wait_tasks = []
        for dep in deps:
            if dep in self.task_events:
                # Add event waiter for each dependency - non-blocking until await
                wait_tasks.append(self.task_events[dep].wait())

        # Concurrent waiting: waits for ALL dependency events simultaneously
        # Much more efficient than sequential waiting or polling loops
        if wait_tasks:
            await asyncio.gather(*wait_tasks)  # Blocks until all dependencies complete

    async def _any_dependency_failed(self, deps: List[str]) -> bool:
        """
        Dependency failure detection: checks if any prerequisite task failed or was skipped.
        Used for failure propagation - prevents execution of tasks with failed dependencies.
        """
        # Thread-safe status checking: prevents race conditions during status updates
        async with self._lock:
            for dep in deps:
                status = self.task_statuses.get(dep)
                # Failure conditions: both explicit failures and dependency-skipped tasks
                if status in [models.TaskStatus.FAILED, models.TaskStatus.SKIPPED]:
                    return True  # At least one dependency failed
        return False  # All dependencies succeeded

    async def _mark_task_skipped(self, task_id: int, identifier: str) -> None:
        """
        Task skipping: marks task as skipped due to dependency failure.
        Updates database and signals completion to unblock dependent tasks.
        """
        for session in get_session():
            # Database update: persists skip status through CRUD layer (maintains SOLE principle)
            crud.mark_task_skipped(session, task_id)

        # Thread-safe state update and completion signaling
        async with self._lock:
            self.task_statuses[identifier] = models.TaskStatus.SKIPPED  # Update local status
            self.task_events[identifier].set()  # Signal completion to dependent tasks

    async def _mark_task_failed(self, task_id: int, identifier: str, error: str) -> None:
        """
        Task failure handling: marks task as failed with error details.
        Updates database and signals completion to unblock dependent tasks.
        """
        for session in get_session():
            # Database failure recording: persists failure status and error message
            crud.mark_task_failed(session, task_id, error)  # CRUD layer maintains SOLE principle

        # Thread-safe state update and completion signaling
        async with self._lock:
            self.task_statuses[identifier] = models.TaskStatus.FAILED  # Update local status
            self.task_events[identifier].set()  # Signal completion to dependent tasks

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
        """
        Orchestration completion: calculates final statistics and updates database.
        Determines overall success/failure based on task outcomes and persists summary.
        """
        # Statistics calculation: counts task outcomes for orchestration summary
        completed = 0
        failed = 0
        skipped = 0

        # Thread-safe statistics collection: prevents race conditions during counting
        async with self._lock:
            for status in self.task_statuses.values():
                if status == models.TaskStatus.COMPLETED:
                    completed += 1
                elif status == models.TaskStatus.FAILED:
                    failed += 1
                elif status == models.TaskStatus.SKIPPED:
                    skipped += 1

        # Overall status determination: orchestration succeeds only if no tasks failed
        final_status = "completed" if failed == 0 else "failed"

        # Database finalization: persists orchestration outcome and statistics
        for session in get_session():
            # CRUD layer usage maintains architectural SOLE principle
            crud.update_orchestration_status(
                session,
                self.orchestration_id,
                final_status,
                completed_tasks=completed,
                failed_tasks=failed,
                skipped_tasks=skipped,
            )
