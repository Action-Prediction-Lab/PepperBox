"""Shared helpers for the shim integration guards.

Each guard runs as a script (exit 1 on failure) and under pytest (skipped when no shim answers).
"""
import math
import os
import sys
import time

sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir, "py3-naoqi-bridge"))

from naoqi_proxy import NaoqiClient  # noqa: E402


def connect():
    return NaoqiClient()


def shim_reachable():
    """True if a shim answers on localhost:5000."""
    try:
        NaoqiClient().ALMotion.getRobotPosition(True)
        return True
    except Exception:
        return False


def wrap_angle(radians):
    """Fold an angle difference into (-pi, pi]; getRobotPosition wraps theta."""
    return math.atan2(math.sin(radians), math.cos(radians))


def settled(client, seconds=1.0):
    """Pose sampled twice `seconds` apart, returned as (before, after)."""
    before = client.ALMotion.getRobotPosition(True)
    time.sleep(seconds)
    return before, client.ALMotion.getRobotPosition(True)


def wait_until_still(client, timeout=45.0, tol=0.002, hold=0.6):
    """Poll until the base pose holds steady for `hold` seconds; False on timeout.

    `timeout` is a hang guard, not an expected duration: a 0.8 rad turn takes ~4.8s idle, ~14s loaded.
    """
    deadline = time.time() + timeout
    last = client.ALMotion.getRobotPosition(True)
    still_since = None
    while time.time() < deadline:
        time.sleep(0.2)
        now = client.ALMotion.getRobotPosition(True)
        moved = math.hypot(now[0] - last[0], now[1] - last[1])
        spun = abs(wrap_angle(now[2] - last[2]))
        if moved < tol and spun < tol:
            if still_since is None:
                still_since = time.time()
            elif time.time() - still_since >= hold:
                return True
        else:
            still_since = None
        last = now
    return False


def spin_until(client, target_rad, eps=0.0001, stall_polls=25, poll_s=0.1):
    """Rotate until |dtheta| reaches target_rad; returns the angle turned.

    Gives up on stall rather than elapsed time, so the verdict does not depend on host speed.
    """
    theta = lambda: client.ALMotion.getRobotPosition(True)[2]
    start = last = theta()
    stalled = 0
    while stalled < stall_polls:
        time.sleep(poll_s)
        now = theta()
        if abs(wrap_angle(now - start)) >= target_rad:
            break
        stalled = stalled + 1 if abs(wrap_angle(now - last)) < eps else 0
        last = now
    return abs(wrap_angle(theta() - start))


class Guard:
    """Accumulates named checks and fails once at the end with the full list."""

    def __init__(self, name):
        self.name = name
        self.failures = []

    def check(self, label, ok, detail=""):
        print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" ({detail})" if detail else ""))
        if not ok:
            self.failures.append(label)

    def stationary(self, client, label="base is stationary", tol=0.005, seconds=1.0):
        """Assert the base is not drifting; a lost stop strands the sim walking away."""
        a, b = settled(client, seconds)
        moved = math.hypot(b[0] - a[0], b[1] - a[1])
        spun = abs(wrap_angle(b[2] - a[2]))
        self.check(label, moved <= tol and spun <= tol, f"d={moved:.4f}m dtheta={spun:.4f}rad")

    def finish(self):
        if self.failures:
            raise AssertionError(
                f"{self.name}: {len(self.failures)} check(s) failed: {self.failures}")
        print(f"\n--- {self.name}: all checks passed ---")


def main(fn):
    """Run a guard function as a script, exiting 1 on failure."""
    try:
        fn()
    except AssertionError as exc:
        print(f"\n--- FAILURE ---\n{exc}")
        sys.exit(1)
