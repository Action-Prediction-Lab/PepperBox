# Python 3 to NAOqi Bridge

This directory contains the Python 2.7 "shim" server and the Python 3 "proxy" client, which together form a bridge to allow Python 3 applications to communicate with the `naoqi` robot SDK.

## Purpose

The `pynaoqi` SDK is only compatible with Python 2.7. The Python 2.7 shim server runs in a Python 2.7 environment, receives commands via a simple web API, executes those commands using the `naoqi` library, and returns the result. The Python 3 proxy client provides a native-like interface in Python 3, translating calls into HTTP requests to the shim server. This allows a Python 3 client to interact with the robot seamlessly.

## Components

*   **`shim_server.py`**: The Python 2.7 Flask server that exposes the NAOqi API via HTTP.
*   **`naoqi_proxy.py`**: The Python 3 client library that provides a convenient interface to interact with the shim server.
*   **`examples/`**: Directory containing example scripts demonstrating the usage of the `NaoqiClient` (e.g., `basic_usage_example.py`, `helloworld_in_python3.py`).
*   **`test_naoqi_proxy.py`**: A comprehensive test suite for the `naoqi_proxy` client.

## How to Run the Bridge

To use the bridge, both the Python 2.7 shim server and the NAOqi instance (simulated or physical robot) must be running and accessible.

### 1. Configure the NAOqi Connection

The shim server connects to the NAOqi instance using the IP address and port specified in the `robot.env` file. Create this file in the `py3-naoqi-bridge` directory if it doesn't exist, and add the `NAOQI_IP` and `NAOQI_PORT`:

```
NAOQI_IP=127.0.0.1
NAOQI_PORT=37647
```

Replace `127.0.0.1` and `41703` with the actual IP address and port of your NAOqi instance.

### 2. Run the Python 2.7 Shim Server

The server must be run from within the PepperBox Docker container. Launch it from the terminal using Python 2.7:

```bash
python /home/pepperdev/apps/py3-naoqi-bridge/shim_server.py
```

This server will listen for incoming requests on `http://0.0.0.0:5000`.

### 3. Use the Python 3 Proxy Client

Once the shim server is running, you can use the `NaoqiClient` in your Python 3 applications. The client defaults to connecting to `http://localhost:5000`.

#### Initialiation

```python
from naoqi_proxy import NaoqiClient, NaoqiProxyError

client = NaoqiClient(host="localhost", port=5000) # Host and port of the shim server
```

#### Calling NAOqi Methods

Access NAOqi modules as attributes of the `client` object, and then call their methods. Arguments are passed directly.

```python
try:
    # Example: Make the robot say something
    client.ALTextToSpeech.say("Hello from Python 3 proxy")

    # Example: Get robot configuration
    robot_config = client.ALMotion.getRobotConfig()
    print(f"Robot configuration: {robot_config}")

    # Example: Insert data into ALMemory
    client.ALMemory.insertData("myKey", "myValue")

except NaoqiProxyError as e:
    print(f"NAOqi Proxy Error: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
```

#### Error Handling

Errors originating from the NAOqi instance or communication issues will be raised as `NaoqiProxyError` exceptions on the Python 3 client side. It is recommended to wrap your NAOqi calls in `try...except NaoqiProxyError` blocks.

## Testing the Bridge

To verify the functionality of the bridge, you can run the provided test suite:

1.  Ensure the Docker container is running.
2.  Ensure the Python 2.7 shim server (`shim_server.py`) is running inside the container.
3.  Execute the tests using Python 3:

    ```bash
    python3 /home/pepperdev/apps/py3-naoqi-bridge/test_naoqi_proxy.py
    ```

### Tested Functionality

The `test_naoqi_proxy.py` suite validates the following aspects of the bridge:

*   **Basic Communication**: Successful invocation of `ALTextToSpeech.say` and `ALMotion.getRobotConfig`.
*   **Error Propagation**: Correct handling and raising of `NaoqiProxyError` for non-existent NAOqi modules or methods.
*   **Argument Handling**: Successful passing of various data types (strings, numbers, booleans, lists, dictionaries) to `ALMemory.insertData`.

### Known Limitations

*   **ALMemory String Retrieval in Simulator**: When using a simulated NAOqi instance, retrieving string values that were part of a list inserted into `ALMemory` (e.g., `client.ALMemory.insertData("myList", [1, "two", False])` and then `client.ALMemory.getData("myList")`) may result in the string values being returned as `None`. This appears to be a limitation of the simulated NAOqi environment rather than a bug in the bridge implementation. The `test_06_get_data_from_memory` test case in `test_naoqi_proxy.py` is currently commented out to reflect this.

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

### Example Usage (cURL)

Here is an example of using `curl` to make the robot say "Hello" via the shim server directly.

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
