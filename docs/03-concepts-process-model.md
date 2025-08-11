# Process Isolation Model

A core feature of Claude Worker is its resilience to crashes. A single, misbehaving task should not be able to bring down the entire server or affect other tasks. This is achieved through **process isolation**, using Python's built-in `concurrent.futures.ProcessPoolExecutor`.

## How It Works

When the Claude Worker server starts, it initializes a `ProcessPoolExecutor` in `server/main.py`:

```python
# src/server/main.py
executor_pool = ProcessPoolExecutor(max_workers=4)
```

This creates a pool of 4 reusable worker processes that are managed by the main server process.

When a new task is submitted via the API, the server does not execute it directly. Instead, it submits the task to the process pool:

```python
# src/server/main.py
executor_pool.submit(run_task_in_worker, db_task.id)
```

The `ProcessPoolExecutor` then takes over:

1.  It picks an available worker process from the pool.
2.  It sends the function (`run_task_in_worker`) and its argument (`db_task.id`) to that worker process.
3.  The worker process executes the function completely independently of the main server process.

## The Key Benefit: Crash Protection

Because each task runs in a separate OS process, it has its own memory space. If a task encounters a fatal error (e.g., a segmentation fault from a native library, or an unhandled exception that crashes the process), only that single worker process will terminate.

The main server process, which is only responsible for handling API requests and managing the pool, remains unaffected. The `ProcessPoolExecutor` will even automatically replace the crashed worker process with a new one, ensuring the pool remains healthy for future tasks.

This model provides robust protection against:
*   Memory leaks in a single task.
*   CPU-intensive tasks that become unresponsive.
*   Unexpected crashes in the Claude Code SDK or its dependencies.

## A Key Technical Constraint: Pickling

A critical detail of inter-process communication in Python is **pickling**. To send the `run_task_in_worker` function and its arguments from the main process to a worker process, Python must serialize them into a byte stream. This process is called "pickling".

This imposes a key constraint on our design: **the function submitted to the pool must be a top-level function.**

You cannot submit an instance method or a nested function defined inside another function, because Python's pickler wouldn't know how to find and reconstruct it in the other process.

This is why `run_task_in_worker` is defined at the top level of the `server/main.py` module:

```python
# src/server/main.py

# Worker process entry point (must be top-level for pickling)
def run_task_in_worker(task_id: int):
    """
    Entry point for worker processes.
    Creates TaskExecutor and runs the async task.
    """
    executor = TaskExecutor(task_id)
    asyncio.run(executor.run())
```

This design choice is a direct consequence of using a process-based concurrency model and reveals an important technical trade-off made for the sake of robustness.