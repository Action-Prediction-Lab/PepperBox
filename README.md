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

To start an interactive session in the container with host networking (required for easy connection to Choregraphe on the host):

```bash
./run.sh
```

This will:
1.  Start the container with `--net=host`.
2.  Launch the `shim_server` (Flask app) on port 5000.

### Connection Details
The shim server listens on **port 5000**.
It exposes the `Naoqi` API (proxy) to control the simulated robot using `qibullet`.

By default, it is configured to listen for commands that it proxies to the simulator.

## Simulation (Optional)

If you wish to run the **qibullet** simulator inside the container, follow these steps.

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
