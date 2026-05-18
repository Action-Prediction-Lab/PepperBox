from unittest.mock import MagicMock
import pytest
from adapters.base import GenericAdapter, StubAdapter, stub
from post_tasks import TaskRegistry


# --- @stub decorator ---

def test_stub_decorator_marks_function():
    @stub()
    def f():
        return 7
    assert f() == 7
    assert getattr(f, "_sim_stub", False) is True


def test_stub_decorator_preserves_name():
    @stub()
    def my_method():
        pass
    assert my_method.__name__ == "my_method"


# --- GenericAdapter ---

def test_generic_falls_through_to_pepper_for_existing_method():
    pepper = MagicMock()
    pepper.someMethod.return_value = "qibullet-result"
    adapter = GenericAdapter(pepper, TaskRegistry())
    assert adapter.someMethod("arg") == "qibullet-result"
    pepper.someMethod.assert_called_once_with("arg")


def test_generic_raises_for_missing_pepper_method():
    pepper = MagicMock(spec=[])  # spec=[] makes hasattr return False for everything
    adapter = GenericAdapter(pepper, TaskRegistry())
    with pytest.raises(AttributeError, match="PepperVirtual has no method"):
        adapter.nonExistent


def test_generic_blocks_underscore_prefix():
    pepper = MagicMock()
    adapter = GenericAdapter(pepper, TaskRegistry())
    with pytest.raises(AttributeError, match="is private"):
        adapter._secret


def test_generic_blocks_loadrobot():
    pepper = MagicMock()
    pepper.loadRobot = MagicMock()  
    adapter = GenericAdapter(pepper, TaskRegistry())
    with pytest.raises(AttributeError, match="is blocked"):
        adapter.loadRobot


def test_generic_post_runs_target_and_returns_task_id():
    pepper = MagicMock()
    pepper.someMethod.return_value = "done"
    registry = TaskRegistry()
    adapter = GenericAdapter(pepper, registry)
    task_id = adapter.post("someMethod", "arg")
    assert isinstance(task_id, int)
    assert registry._tasks[task_id]["result"] == "done"
    pepper.someMethod.assert_called_once_with("arg")


def test_generic_post_propagates_unknown_target():
    pepper = MagicMock(spec=[])
    adapter = GenericAdapter(pepper, TaskRegistry())
    with pytest.raises(AttributeError):
        adapter.post("nonExistent", "arg")


def test_generic_subclass_method_takes_precedence_over_fallthrough():
    """If a subclass defines a method, it must be called instead of falling
    through to pepper. This protects against accidentally using
    __getattribute__ instead of __getattr__ in the base class."""

    class MySubclass(GenericAdapter):
        def myMethod(self):
            return "from-subclass"

    pepper = MagicMock()
    pepper.myMethod.return_value = "from-pepper"
    adapter = MySubclass(pepper, TaskRegistry())

    assert adapter.myMethod() == "from-subclass"
    pepper.myMethod.assert_not_called()


def test_generic_post_forwards_multiple_args_and_kwargs():
    """post must forward arbitrary positional and keyword arguments to the
    target. Live callers pass complex payloads (e.g. lookAt takes a point
    list, two floats, and a bool)."""
    pepper = MagicMock()
    adapter = GenericAdapter(pepper, TaskRegistry())
    adapter.post("multiArgMethod", 1, "two", 3.0, flag=True, mode="x")
    pepper.multiArgMethod.assert_called_once_with(1, "two", 3.0, flag=True, mode="x")


# --- StubAdapter ---

def test_stub_adapter_returns_default():
    adapter = StubAdapter(default=None, task_registry=TaskRegistry())
    assert adapter.anyMethod("ignored") is None


def test_stub_adapter_marks_returned_callable():
    adapter = StubAdapter(default=None, task_registry=TaskRegistry())
    stub_callable = adapter.anyMethod
    assert getattr(stub_callable, "_sim_stub", False) is True


def test_stub_adapter_uses_per_method_override():
    adapter = StubAdapter(
        default=None,
        overrides={"getMode": "Head"},
        task_registry=TaskRegistry(),
    )
    assert adapter.getMode() == "Head"
    assert adapter.someOtherMethod() is None


def test_stub_adapter_post_runs_stub_target():
    registry = TaskRegistry()
    adapter = StubAdapter(default=None, task_registry=registry)
    task_id = adapter.post("anyMethod", "arg")
    assert isinstance(task_id, int)
    assert registry._tasks[task_id]["result"] is None
