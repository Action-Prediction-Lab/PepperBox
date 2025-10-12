#!/bin/bash

# Detect if the host has an NVIDIA GPU
if [ -x "$(command -v nvidia-smi)" ]; then
    echo "NVIDIA GPU detected. Configuring for NVIDIA runtime."
    DOCKER_ARGS="--gpus all \
                 -e NVIDIA_DRIVER_CAPABILITIES=all \
                 -e NVIDIA_VISIBLE_DEVICES=all"
else
    echo "No NVIDIA GPU detected. Using default GPU settings."
    DOCKER_ARGS="--gpus all"
fi

docker run -it \
    -e DISPLAY=$DISPLAY \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    $DOCKER_ARGS \
    --name pepper-container \
    pepper-direct-env
