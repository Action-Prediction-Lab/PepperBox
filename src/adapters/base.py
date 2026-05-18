"""Adapter base classes and the @stub decorator.

GenericAdapter wraps a qibullet `PepperVirtual` and dispatches NAOqi-shaped
method calls. Methods that exist on `pepper` fall through via `__getattr__`
(overrides defined on subclasses take precedence). Unknown methods raise
AttributeError, which the dispatcher surfaces as HTTP 500.

StubAdapter is for whole-module no-ops (modules where qibullet has no
analogue at all). Every method returns the declared default (or a
per-method override), tagged with `_sim_stub = True` so the dispatcher can
set the `X-Sim-Stub` response header.

@stub marks individual methods on modeled adapters as sim no-ops without
making the whole adapter a StubAdapter.
"""

import functools


def stub(default=None):
    """Mark a method as a sim stub.

    Sets `_sim_stub = True` on the wrapper so the dispatcher can flag the
    response. The `default` argument is documentation only; pass it to
    record the intended return value at the decoration site.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper._sim_stub = True
        return wrapper
    return decorator


class GenericAdapter:
    """Wraps qibullet's PepperVirtual. Subclasses add overrides and stubs."""

    _BLOCKED_NAMES = frozenset({"loadRobot"})

    def __init__(self, pepper, task_registry):
        self._pepper = pepper
        self._tasks = task_registry

    def post(self, target_method, *args, **kwargs):
        """NAOqi `post` dispatch. Runs target synchronously, returns task ID."""
        target = getattr(self, target_method)
        return self._tasks.submit_sync(target, args, kwargs)

    def __getattr__(self, name):
        # __getattr__ runs only when normal lookup fails, so overrides
        # defined on subclasses are reached first.
        if name.startswith("_"):
            raise AttributeError("{!r} is private".format(name))
        if name in self._BLOCKED_NAMES:
            raise AttributeError("{!r} is blocked".format(name))
        if not hasattr(self._pepper, name):
            raise AttributeError("PepperVirtual has no method {!r}".format(name))
        return getattr(self._pepper, name)


class StubAdapter:
    """For modules where every method is a no-op in sim.

    `default` is the return value for any method not in `overrides`.
    `overrides` maps method name -> return value for methods that need a
    specific non-default response.
    """

    def __init__(self, default=None, overrides=None, task_registry=None):
        self._default = default
        self._overrides = overrides or {}
        self._tasks = task_registry

    def post(self, target_method, *args, **kwargs):
        target = getattr(self, target_method)
        return self._tasks.submit_sync(target, args, kwargs)

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError("{!r} is private".format(name))
        return_value = self._overrides.get(name, self._default)

        def stub_method(*args, **kwargs):
            return return_value

        stub_method._sim_stub = True
        return stub_method
