# Python 3 to NAOqi Bridge

This directory contains the Python 2.7 "shim" server, which acts as a bridge to allow Python 3 applications to communicate with the `naoqi` robot SDK.

## Purpose

The `pynaoqi` SDK is only compatible with Python 2.7. This server runs in the Python 2.7 environment, receives commands via a simple web API, executes those commands using the `naoqi` library, and returns the result. This allows a Python 3 client to interact with the robot seamlessly.

## How to Run the Server

The server must be run from within the PepperBox Docker container. It requires two environment variables to be set to specify the IP address and port of the simulated (or real) robot.

1.  **Find the Robot IP and Port:** Open the Choregraphe application and find the connection details in the "Robot view". The port is often dynamic and changes each time Choregraphe is started.

2.  **Run the server:** Launch the server from the terminal, passing it the correct IP and Port.

    ```bash
    NAOQI_IP=<robot_ip_address> NAOQI_PORT=<robot_port> python /home/pepperdev/apps/py3-naoqi-bridge/shim_server.py
    ```
    For example:
    ```bash
    NAOQI_IP=172.17.0.2 NAOQI_PORT=44677 python /home/pepperdev/apps/py3-naoqi-bridge/shim_server.py
    ```

## API Reference

### Endpoint: `/api/call`

*   **Method:** `POST`
*   **Content-Type:** `application/json`

### Request Payload

The request body must be a JSON object with the following fields:

*   `module` (string, required): The name of the `naoqi` module to call (e.g., `"ALTextToSpeech"`).
*   `method` (string, required): The name of the method to call on the module (e.g., `"say"`).
*   `args` (array, optional): A list of positional arguments to pass to the method. Defaults to `[]`.
*   `kwargs` (object, optional): A dictionary of keyword arguments to pass to the method. Defaults to `{}`.

### Example Usage

Here is an example of using `curl` to make the robot say "Hello".

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
