# py3-naoqi-bridge/stop_signals.py (Python 2)
"""SIGTERM and SIGINT handling for the bridge services: the first stop signal raises KeyboardInterrupt and the service ignores every later one."""
import signal


def raise_once(signum, frame):
    """Ignores further SIGTERM and SIGINT, then raises KeyboardInterrupt."""
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    raise KeyboardInterrupt


def catch_stop_signals():
    """Makes the first SIGTERM or SIGINT raise KeyboardInterrupt in the main thread."""
    signal.signal(signal.SIGTERM, raise_once)
    signal.signal(signal.SIGINT, raise_once)
