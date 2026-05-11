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

    # pynaoqi is proprietary and never baked into the image; the host supplies
    # it via bind-mount at /opt/pynaoqi-python2.7-2.5.7.1-linux64 (see run.sh /
    # the dev-overlay compose). Fail fast with a friendly message rather than
    # letting Python 2 emit an ImportError six frames deep.
    NAOQI_PY="/opt/pynaoqi-python2.7-2.5.7.1-linux64/lib/python2.7/site-packages/naoqi.py"
    if [ ! -f "$NAOQI_PY" ]; then
        cat >&2 <<EOF
[Entrypoint] ERROR: pynaoqi SDK not mounted

The physical-robot bridge needs SoftBank Robotics' pynaoqi mounted at
/opt/pynaoqi-python2.7-2.5.7.1-linux64 inside the container. Default host
location is \$HOME/.pepperbox/pynaoqi-python2.7-2.5.7.1-linux64, populated by
running ./setup.sh on the host.

Looked for: $NAOQI_PY
EOF
        exit 1
    fi

    NAOQI_PORT=${NAOQI_PORT:-9559}
    if ! python2 -c "
import socket, sys
s = socket.socket()
s.settimeout(3)
try:
    s.connect(('$NAOQI_IP', $NAOQI_PORT))
except Exception as exc:
    sys.stderr.write('connect failed: %s\n' % exc)
    sys.exit(1)
" >/dev/null 2>&1; then
        cat >&2 <<EOF
[Entrypoint] ERROR: cannot reach NAOqi at $NAOQI_IP:$NAOQI_PORT

Check: robot powered on, on the same network, NAOQI_IP / NAOQI_PORT correct
in robot.env, and no firewall between the host and the robot.
EOF
        exit 1
    fi

    python2 py3-naoqi-bridge/video_streamer.py &
    python2 py3-naoqi-bridge/shim_server.py
fi
