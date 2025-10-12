# PepperBox

This repository contains a Dockerized environment for developing applications for Aldebaran's NAO and Pepper robots, using Choregraphe and the `pynaoqi` Python SDK.

## Prerequisites

- Docker
- NVIDIA GPU with the latest drivers (for hardware acceleration)

## Build the Docker Image

To build the Docker image, run the following command from the root of the project directory:

```bash
docker build -t pepper-direct-env .
```

## Run the Container

To start an interactive session in the container, run the following script:

```bash
./run.sh
```

This will give you a bash shell inside the container. From there, you can start Choregraphe by running:

```bash
/opt/choregraphe/choregraphe
```
