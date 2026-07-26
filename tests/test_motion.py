"""Integration guard: joint command/read-back, posture, and that stopMove halts the base.

Requires a running shim (./run.sh). Run as a script or under pytest.
"""
import time

from guard import Guard, connect, shim_reachable, main

try:
    import pytest
    pytestmark = pytest.mark.skipif(not shim_reachable(), reason="requires a running shim")
except ImportError:
    pass

JOINT_TOL_RAD = 0.02


def test_motion():
    g = Guard("motion")
    client = connect()

    # Commanded joint angles must come back from the read-back path.
    client.ALMotion.setAngles(["HeadYaw"], [0.5], 0.3)
    time.sleep(2.0)
    read = client.ALMotion.getAngles(["HeadYaw"], True)
    g.check("getAngles returns a list", isinstance(read, list) and len(read) == 1, f"{read}")
    if isinstance(read, list) and read:
        g.check("HeadYaw tracks command", abs(read[0] - 0.5) <= JOINT_TOL_RAD,
                f"cmd=0.500 read={read[0]:.3f}")

    # qibullet returns a scalar for a single joint; the adapter must still hand back a list.
    single = client.ALMotion.getAngles("HeadYaw", True)
    g.check("getAngles wraps a scalar into a list", isinstance(single, list), f"{single}")

    client.ALMotion.setAngles(["HeadYaw"], [0.0], 0.3)
    time.sleep(1.5)

    g.check("goToPosture Stand succeeds",
            client.ALRobotPosture.goToPosture("Stand", 0.5) is True)

    # A rotation must actually stop; a lost stop walks the sim off the world.
    client.ALMotion.move(0.0, 0.0, 0.5)
    time.sleep(2.0)
    client.ALMotion.stopMove()
    g.stationary(client, "base halts after stopMove")

    g.finish()


if __name__ == "__main__":
    main(test_motion)
