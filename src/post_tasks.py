"""Task registry for the sim shim's `post` dispatch.

qibullet has no async dispatch, so `submit_sync` runs targets synchronously and reports "already done" to `wait`, with monotonic never-reused int IDs in LRU-bounded storage (default 100k).
"""

import threading
from collections import OrderedDict


class TaskRegistry:
    MAX_ENTRIES = 100_000
    # Hardcoded; making it config-tunable is deferred until it blocks something.

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
