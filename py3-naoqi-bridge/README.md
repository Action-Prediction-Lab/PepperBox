# Python 3 to NAOqi Bridge

This directory contains the Python 2.7 "shim" server and the Python 3 "proxy" client. When put together they form a bridge to allow Python 3 applications to communicate with the `naoqi` robot SDK.

## Purpose

The `pynaoqi` SDK is only compatible with Python 2.7. The Python 2.7 shim server runs in a Python 2.7 environment, receives commands via a simple web API, executes those commands using the `naoqi` library, and returns the result. The Python 3 proxy client provides a native-like interface in Python 3, translating calls into HTTP requests to the shim server. This allows a Python 3 client to interact with the robot seamlessly.

## Components

*   **`shim_server.py`**: The Python 2.7 Flask server that exposes the NAOqi API via HTTP.
*   **`naoqi_proxy.py`**: The Python 3 client library that provides an interface to interact with the shim server. Exposes the optional `warn_on_stubs` flag and `SimStubWarning` class for sim-mode introspection.
*   **`examples/`**: Directory containing example scripts demonstrating the usage of the `NaoqiClient` (e.g., `basic_usage_example.py`, `helloworld_in_python3.py`).
*   **`tests/`**: Unit and integration tests. `test_audio_publisher.py` covers the ZMQ audio publisher; `test_motion.py` is a scripted integration test against a running shim; `test_sim_stub_warning.py` covers the client-side opt-in warning behavior with mocked HTTP responses.

## Using the NaoqiClient

The shim server is launched by the project-level `./run.sh` — see the top-level README for setup and configuration (`NAOQI_IP`, `NAOQI_PORT`, `robot.env`, etc.). Once the shim is running on port 5000, Python 3 code uses the `NaoqiClient` to interface.

### Initialisation

```python
from naoqi_proxy import NaoqiClient, NaoqiProxyError

client = NaoqiClient(host="localhost", port=5000)
```

Optional sim-mode introspection:

```python
client = NaoqiClient(warn_on_stubs=True)   # produce SimStubWarning on stub responses
# or set NAOQI_SIM_WARN_STUBS=1 in the environment
```

### Calling NAOqi Methods

NAOqi modules are accessed as attributes of the client; methods are called directly with positional and keyword arguments.

```python
try:
    client.ALTextToSpeech.say("Hello from Python 3 proxy")
    robot_config = client.ALMotion.getRobotConfig()
    client.ALMemory.insertData("myKey", "myValue")
except NaoqiProxyError as e:
    print(f"NAOqi Proxy Error: {e}")
```

Errors from the shim or the underlying NAOqi instance surface as `NaoqiProxyError`. Wrap calls in `try...except NaoqiProxyError` blocks.

## Testing the Bridge

Unit tests for the client library and the audio publisher run inside the pepper-box container via the project-wide wrapper:

```bash
./tests/run-in-docker.sh py3-naoqi-bridge/tests/test_sim_stub_warning.py -v
./tests/run-in-docker.sh py3-naoqi-bridge/tests/test_audio_publisher.py -v
```

The scripted integration test `tests/test_motion.py` requires a running shim and a real or simulated robot.

For the wider sim-side test suite (adapters, dispatcher, Flask routes) see the top-level `tests/unit/` directory and the project root README.

## API Reference (Shim Server)

### Endpoint: `/api/call`

*   **Method:** `POST`
*   **Content-Type:** `application/json`

### Request Payload

The request body must be a JSON object with the following fields:

*   `module` (string, required): The name of the `naoqi` module to call (e.g., `"ALTextToSpeech"`).
*   `method` (string, required): The name of the method to call on the module (e.g., `"say"`).
*   `args` (array, optional): A list of positional arguments to pass to the method. Defaults to `[]`.
*   `kwargs` (object, optional): A dictionary of keyword arguments to pass to the method. Defaults to `{}`.

### Example Usage (curl)

Here is an example of using `curl` to make the robot say "Hello, world!" via the shim server directly.

```bash
curl -X POST \
     -H "Content-Type: application/json" \
     -d '''{"module": "ALTextToSpeech", "method": "say", "args": ["Hello, world!"]}''' \
     http://localhost:5000/api/call
```

### Responses

*   **Success:** A successful call will return a `200 OK` status with a JSON object containing the result of the method call. If the method has no return value, the result will be `null`.
    ```json
    {"result": null}
    ```

*   **Error:** A failed call will return a `500 Internal Server Error` or `400 Bad Request` status with a JSON object containing the error message.
    ```json
    {"error": "Description of the error..."}
    ```
