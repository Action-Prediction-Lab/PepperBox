import json
import os
import urllib.request
import urllib.error
import warnings


class NaoqiProxyError(Exception):
    """Raised when the shim returns an error response."""


class SimStubWarning(UserWarning):
    """Triggered when the sim shim returns a stub (no-op) response and the
    client has opted into stub-aware warnings via `warn_on_stubs=True` or
    the `NAOQI_SIM_WARN_STUBS=1` env var."""


class NaoqiModule:
    def __init__(self, client, module_name):
        self._client = client
        self._module_name = module_name

    def __getattr__(self, method_name):
        def method_caller(*args, **kwargs):
            success, result, error_message = self._client._call_shim(
                self._module_name, method_name, args, kwargs
            )
            if not success:
                raise NaoqiProxyError(error_message)
            return result
        return method_caller

class NaoqiClient:
    def __init__(self, host="localhost", port=5000, warn_on_stubs=None):
        self._shim_url = f"http://{host}:{port}/api/call"
        if warn_on_stubs is None:
            warn_on_stubs = os.environ.get("NAOQI_SIM_WARN_STUBS", "").lower() in (
                "1", "true", "yes"
            )
        self._warn_on_stubs = warn_on_stubs

    def __getattr__(self, module_name):
        return NaoqiModule(self, module_name)

    def _call_shim(self, module, method, args, kwargs):
        payload = {
            "module": module,
            "method": method,
            "args": list(args),
            "kwargs": kwargs,
        }
        req = urllib.request.Request(
            self._shim_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req) as response:
                response_data = json.loads(response.read().decode("utf-8"))
                if self._warn_on_stubs and self._is_sim_stub(response):
                    warnings.warn(
                        "{}.{} is a sim stub (no qibullet equivalent); "
                        "returning {!r}".format(module, method, response_data.get("result")),
                        SimStubWarning,
                        stacklevel=3,
                    )
                if response.status == 200:
                    return True, response_data.get("result"), None
                return False, None, response_data.get("error", "Unknown error")
        except urllib.error.HTTPError as e:
            error_message = f"HTTP Error {e.code}: {e.reason}"
            try:
                error_data = json.loads(e.read().decode("utf-8"))
                error_message += f" - {error_data.get('error', 'No error details')}"
            except json.JSONDecodeError:
                pass
            return False, None, error_message
        except urllib.error.URLError as e:
            return False, None, f"URL Error: {e.reason}"
        except json.JSONDecodeError:
            return False, None, "Failed to decode JSON response from shim server."
        except SimStubWarning:
            # Let SimStubWarning propagate even if it's been turned into an errorbby the warnings filter.
            raise
        except Exception as e:
            return False, None, f"An unexpected error occurred: {e}"

    @staticmethod
    def _is_sim_stub(response):
        try:
            return response.headers.get("X-Sim-Stub") == "1"
        except Exception:
            return False
