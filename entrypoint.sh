#!/bin/bash

# Default to Simulation if not specified
MODE=${SIMULATION_MODE:-"true"}
NAOQI_IP=${NAOQI_IP:-"127.0.0.1"}

# If NAOQI_IP is NOT local, assume we want to connect to a real robot
if [ "$NAOQI_IP" != "127.0.0.1" ] && [ "$NAOQI_IP" != "localhost" ]; then
    echo "[Entrypoint] Remote IP detected ($NAOQI_IP). Switching to PHYSICAL ROBOT mode."
    MODE="false"
fi

if [ "$MODE" = "true" ]; then
    echo "[Entrypoint] Starting SIMULATION (qibullet)..."
    echo "   - Ensure you have run 'python3 src/setup_wizard.py' at least once."
    python3 src/shim_server.py
else
    echo "[Entrypoint] Starting PHYSICAL ROBOT Bridge (pynaoqi)..."
    echo "   - Target: $NAOQI_IP:$NAOQI_PORT"
    python2 py3-naoqi-bridge/video_streamer.py &
    python2 py3-naoqi-bridge/shim_server.py
fi
