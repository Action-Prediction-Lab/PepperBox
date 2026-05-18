"""Task registry for the sim shim's `post` dispatch.

NAOqi's `post` returns a task ID that callers later query via `wait` or
`getCurrentPosition`. qibullet has no async dispatch, so we run targets
synchronously and treat the resulting state as "already done".

Monotonic int IDs (never reused) so a slow caller's stale task_id never
aliases to a new task. LRU-bounded storage (default 100k) caps memory in
long-running sim sessions.
"""

import threading
from collections import OrderedDict


class TaskRegistry:
    MAX_ENTRIES = 100_000
    # LRU-bounded storage is hardcoded and not tunable from in config. Not a priority until this is blocking. 

    def __init__(self):
        self._lock = threading.Lock()
        self._next_id = 1
        self._tasks = OrderedDict()

    def submit_sync(self, callable_, args, kwargs):
        """Run `callable_` synchronously, store result, return a fresh task ID."""
        with self._lock:
            task_id = self._next_id
            self._next_id += 1
            while len(self._tasks) >= self.MAX_ENTRIES:
                self._tasks.popitem(last=False)
        try:
            result = callable_(*args, **kwargs)
            self._tasks[task_id] = {"done": True, "result": result, "error": None}
        except Exception as e:
            self._tasks[task_id] = {"done": True, "result": None, "error": str(e)}
        return task_id

    def wait(self, task_id, timeout_ms=None):
        """Return True if the task is done. Unknown task IDs return False."""
        task = self._tasks.get(task_id)
        return task is not None and task["done"]
