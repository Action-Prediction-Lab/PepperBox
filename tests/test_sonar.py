"""Integration guard: sonar and laser readings have the right shape and a live range.

Requires a running shim (./run.sh). Run as a script or under pytest.
"""
from guard import Guard, connect, shim_reachable, main

try:
    import pytest
    pytestmark = pytest.mark.skipif(not shim_reachable(), reason="requires a running shim")
except ImportError:
    pass

MAX_RANGE_M = 3.0
LASER_RAYS = 15

FRONT = "Device/SubDeviceList/Platform/Front/Sonar/Sensor/Value"
BACK = "Device/SubDeviceList/Platform/Back/Sonar/Sensor/Value"
LASER_FRONT = "Device/SubDeviceList/Platform/Laser/Front/Sensor/Value"


def test_sonar():
    g = Guard("sonar")
    client = connect()
    client.ALLaser.show(True)

    for label, key in (("front", FRONT), ("back", BACK)):
        value = client.ALMemory.getData(key)
        # 0.0 is what an unscanned laser reports, indistinguishable from an obstacle at contact.
        g.check(f"{label} sonar is a live range",
                isinstance(value, float) and 0.0 < value <= MAX_RANGE_M, f"{value}")

    rays = client.ALMemory.getData(LASER_FRONT)
    g.check("front laser returns a list", isinstance(rays, list), f"{type(rays).__name__}")
    if isinstance(rays, list):
        g.check(f"front laser returns {LASER_RAYS} rays", len(rays) == LASER_RAYS, f"{len(rays)}")
        g.check("laser rays are floats in range",
                all(isinstance(r, float) and 0.0 <= r <= MAX_RANGE_M for r in rays))

    g.finish()


if __name__ == "__main__":
    main(test_sonar)
