#!/bin/bash
# Run pytest under Python 2.7 inside the pepper-box image, for the physical-robot bridge.
#
# The bridge imports the proprietary `naoqi` SDK; these tests stub it, so no robot is needed.
# Still needs hardware: that ALProxy connects, that ALModule.autoBind registers processRemote, and the broker reverse path.
#
# Usage: ./tests/run-py2-in-docker.sh [pytest-args...]
#   ./tests/run-py2-in-docker.sh tests/py2/test_shim_server.py -v
#
# Python 2 tests live in py3-naoqi-bridge/tests/py2/; the rest of that directory is Python 3.

set -e

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Default to the py2 suite unless the caller named a path; a bare flag must not displace it.
ARGS=("$@")
for arg in "$@"; do
    case "$arg" in -*) ;; *) HAS_PATH=1 ;; esac
done
[ -n "$HAS_PATH" ] || ARGS+=("tests/py2")

exec docker run --rm \
    -v "$REPO_ROOT:/repo" \
    -w /repo/py3-naoqi-bridge \
    ghcr.io/action-prediction-lab/pepper-box:latest \
    bash -c 'python2 -m pip install --quiet --user "pytest<5" >/dev/null 2>&1
             PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python2 -m pytest "$@"' -- "${ARGS[@]}"
