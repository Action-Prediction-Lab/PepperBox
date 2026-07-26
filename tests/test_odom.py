"""Integration guard: odometry tracks commanded rotation and translation, and motion stops.

Requires a running shim (./run.sh). Run as a script or under pytest.
"""
import math

from guard import (Guard, connect, main, shim_reachable, spin_until, wait_until_still,
                   wrap_angle)

try:
    import pytest
    pytestmark = pytest.mark.skipif(not shim_reachable(), reason="requires a running shim")
except ImportError:
    pass

SPIN_RAD_S = 0.5
MIN_SPIN_RAD = 0.05
TURN_RAD = 0.8
TURN_TOL_RAD = 0.08
STEP_M = 0.4
STEP_TOL_M = 0.05


def test_odom():
    g = Guard("odom")
    client = connect()
    client.ALLaser.show(True)

    # Hold a velocity until the base actually turns; the sim steps as its thread is scheduled, so a timed command covers a host-dependent angle.
    client.ALMotion.move(0.0, 0.0, SPIN_RAD_S)
    spun = spin_until(client, MIN_SPIN_RAD)
    client.ALMotion.stopMove()
    g.check("velocity command rotates the base", spun >= MIN_SPIN_RAD, f"dtheta={spun:.3f}rad")
    g.stationary(client, "base halts after a rotation")

    # Unwind so repeated runs do not leave the base at a random heading.
    client.ALMotion.move(0.0, 0.0, -SPIN_RAD_S)
    spin_until(client, spun)
    client.ALMotion.stopMove()

    # moveTo is robot-frame, so measuring mid-turn traces a curve and under-reports; assert the precondition.
    g.check("base still before closed-loop moves", wait_until_still(client))

    # moveTo is a displacement command, so the angle achieved does not depend on sim speed.
    before_theta = client.ALMotion.getRobotPosition(True)[2]
    client.ALMotion.moveTo(0.0, 0.0, TURN_RAD)
    g.check("rotation settles", wait_until_still(client))
    turned = wrap_angle(client.ALMotion.getRobotPosition(True)[2] - before_theta)
    g.check("moveTo turns by the commanded angle", abs(turned - TURN_RAD) <= TURN_TOL_RAD,
            f"turned={turned:.3f}rad commanded={TURN_RAD}rad")
    client.ALMotion.moveTo(0.0, 0.0, -turned)
    wait_until_still(client)

    # Translation must register a displacement of roughly the commanded distance.
    before = client.ALMotion.getRobotPosition(True)
    client.ALMotion.moveTo(STEP_M, 0.0, 0.0)
    g.check("translation settles", wait_until_still(client))
    after = client.ALMotion.getRobotPosition(True)
    moved = math.hypot(after[0] - before[0], after[1] - before[1])
    g.check("moveTo travels the commanded distance", abs(moved - STEP_M) <= STEP_TOL_M,
            f"moved={moved:.3f}m commanded={STEP_M}m")
    g.check("translation holds heading", abs(wrap_angle(after[2] - before[2])) < 0.2,
            f"dtheta={wrap_angle(after[2] - before[2]):.3f}rad")

    # Step back by the distance actually measured, then confirm nothing is still driving.
    client.ALMotion.moveTo(-moved, 0.0, 0.0)
    wait_until_still(client)
    client.ALMotion.stopMove()
    g.stationary(client, "base left stationary")

    g.finish()


if __name__ == "__main__":
    main(test_odom)
