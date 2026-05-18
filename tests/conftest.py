import os
import sys

# Add `src/` to sys.path so imports work in test files. Matches the
# runtime invocation pattern: `python3 src/shim_server.py`.
_SRC = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, "src")
)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
