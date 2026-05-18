import threading
import pytest
from post_tasks import TaskRegistry


def test_submit_returns_monotonic_ids():
    reg = TaskRegistry()
    ids = [reg.submit_sync(lambda: None, (), {}) for _ in range(5)]
    assert ids == [1, 2, 3, 4, 5]


def test_submit_records_result():
    reg = TaskRegistry()
    task_id = reg.submit_sync(lambda x, y: x + y, (2, 3), {})
    assert reg._tasks[task_id]["done"] is True
    assert reg._tasks[task_id]["result"] == 5
    assert reg._tasks[task_id]["error"] is None


def test_submit_records_exception():
    reg = TaskRegistry()
    def boom():
        raise ValueError("explode")
    task_id = reg.submit_sync(boom, (), {})
    assert reg._tasks[task_id]["done"] is True
    assert reg._tasks[task_id]["result"] is None
    assert "explode" in reg._tasks[task_id]["error"]


def test_wait_known_id_returns_true():
    reg = TaskRegistry()
    task_id = reg.submit_sync(lambda: 42, (), {})
    assert reg.wait(task_id) is True


def test_wait_unknown_id_returns_false():
    reg = TaskRegistry()
    assert reg.wait(99999) is False


def test_lru_evicts_oldest_at_max_entries():
    reg = TaskRegistry()
    reg.MAX_ENTRIES = 3
    ids = [reg.submit_sync(lambda: None, (), {}) for _ in range(5)]
    # IDs 1 and 2 should be evicted, 3, 4, 5 retained.
    assert reg.wait(ids[0]) is False  # ID 1 evicted
    assert reg.wait(ids[1]) is False  # ID 2 evicted
    assert reg.wait(ids[2]) is True   # ID 3 retained
    assert reg.wait(ids[3]) is True
    assert reg.wait(ids[4]) is True


def test_ids_remain_monotonic_after_eviction():
    """Eviction must not reuse IDs."""
    reg = TaskRegistry()
    reg.MAX_ENTRIES = 2
    first_ids = [reg.submit_sync(lambda: None, (), {}) for _ in range(2)]
    next_id = reg.submit_sync(lambda: None, (), {})
    assert next_id == 3
    assert next_id not in first_ids


def test_concurrent_submits_get_distinct_ids():
    reg = TaskRegistry()
    seen_ids = []
    lock = threading.Lock()

    def worker():
        for _ in range(50):
            task_id = reg.submit_sync(lambda: None, (), {})
            with lock:
                seen_ids.append(task_id)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(seen_ids) == 200
    assert len(set(seen_ids)) == 200  # all distinct
