"""Dispatcher: looks up the per-module adapter and forwards calls.

Returns (result, is_stub) for the X-Sim-Stub header, and raises AttributeError for unknown, blocked or private names, which the route turns into HTTP 500 carrying the message.
"""


class Dispatcher:

    def __init__(self, module_adapters):
        self._adapters = module_adapters

    def dispatch(self, module, method, args, kwargs):
        adapter = self._adapters.get(module)
        if adapter is None:
            raise AttributeError("No adapter for module {!r}".format(module))

        if method == "post":
            if not args:
                raise AttributeError(
                    "post requires the target method name as first arg"
                )
            target = args[0]
            inner_args = args[1:]
            try:
                result = adapter.post(target, *inner_args, **kwargs)
            except AttributeError as e:
                raise AttributeError(
                    "Module {!r}: {}".format(module, e)
                )
            return result, False

        try:
            handler = getattr(adapter, method)
        except AttributeError as e:
            raise AttributeError(
                "Module {!r}: {}".format(module, e)
            )
        result = handler(*args, **kwargs)
        is_stub = getattr(handler, "_sim_stub", False)
        return result, is_stub
