# PepperBox

This repository contains a Dockerized environment for developing applications for Aldebaran's NAO and Pepper robots, using Choregraphe and the `pynaoqi` Python SDK.

## Prerequisites

- Docker
- NVIDIA GPU with the latest drivers (for hardware acceleration)

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
2.  Launch the `entrypoint.sh` which starts the `shim_server` (Flask app) on port 5000.
3.  Start `avahi-daemon` and `choregraphe`.

### Connecting to the Shim Server

The shim server listens on port 5000.
By default, it connects to the physical robot at `127.0.0.1:9559` (inside the container) or `192.168.0.4:9559`.
You can override this by setting environment variables before running:

```bash
export NAOQI_IP=127.0.0.1
export NAOQI_PORT=43175
./run.sh
```
