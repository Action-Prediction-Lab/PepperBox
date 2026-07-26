"""Adapter base classes and the @stub decorator.

GenericAdapter forwards to a qibullet `PepperVirtual` (unknown methods raise AttributeError), StubAdapter no-ops a module, @stub no-ops a method, and every stub carries `_sim_stub = True` for the `X-Sim-Stub` header.
"""

import functools


def stub():
    """Mark a method as a sim stub via `_sim_stub = True`; the body is the return value."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper._sim_stub = True
        return wrapper
    return decorator


class _PostDispatch:
    """NAOqi `post` dispatch shared by both adapter kinds."""

    def post(self, target_method, *args, **kwargs):
        """Run the target synchronously and return its task ID."""
        target = getattr(self, target_method)
        return self._tasks.submit_sync(target, args, kwargs)


class GenericAdapter(_PostDispatch):
    """Wraps qibullet's PepperVirtual. Subclasses add overrides and stubs."""

    _BLOCKED_NAMES = frozenset({"loadRobot"})

    def __init__(self, pepper, task_registry):
        self._pepper = pepper
        self._tasks = task_registry

    def __getattr__(self, name):
        # Runs only when normal lookup fails, so subclass overrides are reached first.
        if name.startswith("_"):
            raise AttributeError("{!r} is private".format(name))
        if name in self._BLOCKED_NAMES:
            raise AttributeError("{!r} is blocked".format(name))
        if not hasattr(self._pepper, name):
            raise AttributeError("PepperVirtual has no method {!r}".format(name))
        return getattr(self._pepper, name)


class StubAdapter(_PostDispatch):
    """No-ops a whole module: every method returns `overrides[name]` if present, else `default`."""

    def __init__(self, default=None, overrides=None, task_registry=None):
        self._default = default
        self._overrides = overrides or {}
        self._tasks = task_registry

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError("{!r} is private".format(name))
        return_value = self._overrides.get(name, self._default)

        def stub_method(*args, **kwargs):
            return return_value

        stub_method._sim_stub = True
        return stub_method
