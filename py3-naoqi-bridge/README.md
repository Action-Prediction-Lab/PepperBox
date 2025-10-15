# Python 3 to NAOqi Bridge

This directory contains the Python 2.7 "shim" server, which acts as a bridge to allow Python 3 applications to communicate with the `naoqi` robot SDK.

## Purpose

The `pynaoqi` SDK is only compatible with Python 2.7. This server runs in the Python 2.7 environment, receives commands via a simple web API, executes those commands using the `naoqi` library, and returns the result. This allows a Python 3 client to interact with the robot seamlessly.

## How to Run the Server

The server must be run from within the PepperBox Docker container. It reads the robot's IP address and port from a `robot.env` file in the same directory.

1.  **Create the `robot.env` file:** Create a file named `robot.env` in the `py3-naoqi-bridge` directory.

2.  **Add the robot's IP and port to the file:** Add the `NAOQI_IP` and `NAOQI_PORT` to the file, like this:

    ```
    NAOQI_IP=192.168.0.4
    NAOQI_PORT=9559
    ```

3.  **Run the server:** Launch the server from the terminal.

    ```bash
    python /home/pepperdev/apps/py3-naoqi-bridge/shim_server.py
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
