import os
import sys

# Add `src/` to sys.path, matching the runtime invocation `python3 src/shim_server.py`.
_SRC = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, "src")
)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
