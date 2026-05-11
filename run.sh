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

# pynaoqi SDK is supplied at runtime, never baked into the image. Run
# ./setup.sh on the host first to populate ~/.pepperbox; that path then
# bind-mounts into the container so the physical-robot bridge can find naoqi.
PEPPERBOX_HOME="${PEPPERBOX_HOME:-$HOME/.pepperbox}"
PYNAOQI_HOST="${PEPPERBOX_HOME}/pynaoqi-python2.7-2.5.7.1-linux64"
PYNAOQI_MOUNT=()
if [ -d "$PYNAOQI_HOST" ]; then
    PYNAOQI_MOUNT=(-v "${PYNAOQI_HOST}:/opt/pynaoqi-python2.7-2.5.7.1-linux64:ro")
else
    echo "Note: pynaoqi SDK not found at ${PYNAOQI_HOST}; physical-robot mode"
    echo "      will refuse to start. Run ./setup.sh first if you have a Pepper."
    echo "      Sim mode (NAOQI_IP=127.0.0.1) is unaffected."
fi

docker run -it --rm \
    --net=host \
    --device /dev/dri \
    -e DISPLAY=$DISPLAY \
    -e NAOQI_IP=${NAOQI_IP:-"127.0.0.1"} \
    -e NAOQI_PORT=${NAOQI_PORT:-9559} \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v $(pwd)/py3-naoqi-bridge:/home/pepperdev/py3-naoqi-bridge \
    -v $(pwd)/src:/home/pepperdev/src \
    -v $(pwd)/.qibullet:/home/pepperdev/.qibullet \
    "${PYNAOQI_MOUNT[@]}" \
    $DOCKER_ARGS \
    --name pepper-qibullet \
    pepper-box:latest \
    /home/pepperdev/entrypoint.sh
