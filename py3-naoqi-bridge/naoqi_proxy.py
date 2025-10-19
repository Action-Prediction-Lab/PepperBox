import json
import urllib.request

class NaoqiProxyError(Exception):
    """Custom exception for errors from the NAOqi shim server."""
    pass

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
    def __init__(self, host="localhost", port=5000):
        self._shim_url = f"http://{host}:{port}/api/call"

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
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )

        try:
            with urllib.request.urlopen(req) as response:
                response_data = json.loads(response.read().decode('utf-8'))
                if response.status == 200:
                    return True, response_data.get("result"), None
                else:
                    error_message = response_data.get("error", "Unknown error from shim server")
                    return False, None, error_message
        except urllib.error.HTTPError as e:
            error_message = f"HTTP Error {e.code}: {e.reason}"
            try:
                error_data = json.loads(e.read().decode('utf-8'))
                error_message += f" - {error_data.get('error', 'No error details')}"
            except json.JSONDecodeError:
                pass # Not a JSON error response
            return False, None, error_message
        except urllib.error.URLError as e:
            return False, None, f"URL Error: {e.reason}"
        except json.JSONDecodeError:
            return False, None, "Failed to decode JSON response from shim server."
        except Exception as e:
            return False, None, f"An unexpected error occurred: {e}"