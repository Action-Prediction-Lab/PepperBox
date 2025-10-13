#!/bin/bash
xhost +local:docker

# Detect if the host has an NVIDIA GPU
if [ -x "$(command -v nvidia-smi)" ]; then
    echo "NVIDIA GPU detected. Configuring for NVIDIA runtime."
    DOCKER_ARGS="--gpus all \
                 -e NVIDIA_DRIVER_CAPABILITIES=all \
                 -e NVIDIA_VISIBLE_DEVICES=all"
else
    echo "No NVIDIA GPU detected. Using default GPU settings."
    DOCKER_ARGS=""
fi

docker run -it --rm \
    -e DISPLAY=$DISPLAY \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v $(pwd)/py3-naoqi-bridge:/home/pepperdev/apps/py3-naoqi-bridge \
    -p 5000:5000 \
    $DOCKER_ARGS \
    --name pepper-container \
    --entrypoint /bin/bash \
    pepper-direct-env