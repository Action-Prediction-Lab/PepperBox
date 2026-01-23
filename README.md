# PepperBox

This repository contains a Dockerised environment for developing applications for Aldebaran's NAO and Pepper robots, with the `pynaoqi` Python SDK, with the `qiBullet` simulator.

## Prerequisites

- Docker

## Build the Docker Image

To build the Docker image, run the following command from the root of the project directory:

```bash
docker build -t jwgcurrie/pepper-box:01-26-latest .
```

## Run the Container

## Run the Container

To start the environment:

```bash
./run.sh
```

The container uses `entrypoint.sh` to automatically select the mode:

1.  **Simulation Mode (Default)**:
    *   If `NAOQI_IP` is unset or `localhost`, it launches **qibullet** (Python 3).
    *   Requires `python3 src/setup_wizard.py` to be run once.

2.  **Physical Robot Mode**:
    *   If `NAOQI_IP` is set to a remote address (e.g., Robot IP), it launches the **pynaoqi bridge** (Python 2).
    *   Example:
        ```bash
        export NAOQI_IP=192.168.1.100
        ./run.sh
        ```

### Connection Details
The **Shim Server** (port 5000) is your unified endpoint.
*   **Simulation**: Proxies to internal qibullet.
*   **Physical**: Proxies to the real robot via `pynaoqi`.

Your client code (Python 3) does not need to know the difference.

### First Time Setup (Simulation Only)
If utilizing the simulator, you must install assets once:
```bash
# Inside container
python3 src/setup_wizard.py
```
