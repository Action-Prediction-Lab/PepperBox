#!/bin/bash
xhost +local:docker

# Debug: Check if nvidia-smi exists
if command -v nvidia-smi &> /dev/null; then
    echo "NVIDIA GPU detected via nvidia-smi."
    # Added PRIME offload variables which are often needed for laptops
    DOCKER_ARGS="--gpus all \
                 -e NVIDIA_DRIVER_CAPABILITIES=all \
                 -e NVIDIA_VISIBLE_DEVICES=all \
                 -e __NV_PRIME_RENDER_OFFLOAD=1 \
                 -e __GLX_VENDOR_LIBRARY_NAME=nvidia"
else
    echo "WARNING: nvidia-smi not found. Using software rendering (Mesa)."
    echo "Install nvidia-container-toolkit on host for better performance."
    DOCKER_ARGS=""
fi

# We mount the X11 socket and set DISPLAY for the GUI
# Corrected volume mounts to /home/pepperdev to match Dockerfile
# Added -e USER to fix warning
# Updated for qibullet
docker run -it --rm \
    --net=host \
    --privileged \
    -e DISPLAY=$DISPLAY \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v $(pwd)/py3-naoqi-bridge:/home/pepperdev/py3-naoqi-bridge \
    -v $(pwd)/src:/home/pepperdev/src \
    -v $(pwd)/.qibullet:/root/.qibullet \
    $DOCKER_ARGS \
    --name pepper-qibullet \
    webots-pepper:latest \
    /home/pepperdev/entrypoint.sh
