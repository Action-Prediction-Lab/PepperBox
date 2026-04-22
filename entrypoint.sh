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
    # Auto-seed the qibullet asset cache if the URDF is missing. The cache
    # lives at $HOME/.qibullet and is persisted by a volume mount; the
    # installer writes into a version subdirectory (e.g. 1.4.3/).
    if ! ls "$HOME/.qibullet"/*/pepper.urdf >/dev/null 2>&1; then
        echo "[Entrypoint] qibullet assets missing; seeding via setup_wizard.py..."
        if ! python3 src/setup_wizard.py; then
            echo "[Entrypoint] setup_wizard.py failed. If the cause was 'Permission denied'," >&2
            echo "[Entrypoint] the cache directory is not writable by UID $(id -u)." >&2
            echo "[Entrypoint] Fix on the host: sudo chown -R $(id -u):$(id -g) ../PepperBox/.qibullet/" >&2
            exit 1
        fi
    fi
    python3 src/shim_server.py
else
    echo "[Entrypoint] Starting PHYSICAL ROBOT Bridge (pynaoqi)..."
    echo "   - Target: $NAOQI_IP:$NAOQI_PORT"
    python2 py3-naoqi-bridge/video_streamer.py &
    python2 py3-naoqi-bridge/shim_server.py
fi
