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

To start an interactive session in the container with host networking:

```bash
./run.sh
```

This will:
1.  Start the container with `--net=host`.
2.  Launch the `shim_server` (Flask app) on port 5000.

### Connection Details
The **Shim Server** acts as a bridge between your Python 3 code and the robot. It exposes a JSON API on **port 5000**.

*   **Endpoint**: `http://localhost:5000/api/call`
*   **Method**: `POST`
*   **Payload**: `{"module": "ALMotion", "method": "move", "args": [...]}`

The server proxies these commands to the active backend (either the `qiBullet` simulator or the physical robot via `pynaoqi`).

## Simulation (Optional)
If you wish to run the **qibullet** simulator inside the container:

### 1. First Time Setup
**Important**: Before running the simulation, you must install the proprietary robot assets:

```bash
# Inside the container
python3 src/setup_wizard.py
```
This wizard will download the required meshes from Softbank Robotics after you accept the license.

### 2. Running the Simulator
Once setup is complete, you can launch the simulation server:

```bash
python3 src/shim_server.py
```
