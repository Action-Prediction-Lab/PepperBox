#!/bin/bash
# Run pytest inside the pepper-box container.
#
# Mounts the working tree (src/, tests/, py3-naoqi-bridge/) over the image's
# copies so that we test the current code. Installs pytest at startup
# because the runtime image keeps test deps out.
#
# Usage: ./tests/run-in-docker.sh [pytest-args...]
#   ./tests/run-in-docker.sh tests/unit/ -v
#   ./tests/run-in-docker.sh tests/unit/test_post_tasks.py::test_wait_known_id_returns_true -v

set -e

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

exec docker run --rm \
    -v "$REPO_ROOT/src:/home/pepperdev/src" \
    -v "$REPO_ROOT/tests:/home/pepperdev/tests" \
    -v "$REPO_ROOT/py3-naoqi-bridge:/home/pepperdev/py3-naoqi-bridge" \
    --entrypoint bash \
    ghcr.io/action-prediction-lab/pepper-box:latest \
    -c 'python3 -m pip install --quiet --user pytest && python3 -m pytest "$@"' -- "$@"
