"""ALMotion adapter. Overrides where qibullet's API differs from NAOqi; stubs for NAOqi methods qibullet doesn't model."""

import pybullet
from qibullet.base_controller import PepperBaseController

from .base import GenericAdapter, stub


class ALMotionAdapter(GenericAdapter):

    STOP_TRIES = 5
    STOP_EPS_M_S = 1e-3
    STOP_EPS_RAD_S = 1e-3

    # --- Overrides ---

    def move(self, x, y, theta):
        self._pepper.move(float(x), float(y), float(theta))

    def moveToward(self, x, y, theta):
        # NAOqi normalizes velocity to [-1, 1]; scale to qibullet's m/s and rad/s.
        self._pepper.move(
            float(x) * PepperBaseController.MAX_LINEAR_VELOCITY,
            float(y) * PepperBaseController.MAX_LINEAR_VELOCITY,
            float(theta) * PepperBaseController.MAX_ANGULAR_VELOCITY,
        )

    def moveTo(self, x, y, theta):
        # NAOqi's moveTo is async by default; qibullet's is synchronous, so force async.
        self._pepper.moveTo(float(x), float(y), float(theta), _async=True)

    def stopMove(self):
        # qibullet's stopMove only cancels async moveTo and move(0,0,0) races its async process, so retry until the base reads still.
        for _ in range(self.STOP_TRIES):
            self._pepper.stopMove()
            self._pepper.move(0, 0, 0)
            linear, angular = pybullet.getBaseVelocity(
                self._pepper.robot_model,
                physicsClientId=self._pepper.physics_client)
            # Rotation shows up only in angular; linear alone misses a spin.
            if (max(abs(linear[0]), abs(linear[1])) < self.STOP_EPS_M_S
                    and abs(angular[2]) < self.STOP_EPS_RAD_S):
                return
        # A lost stop strands the base walking forever; zero it directly as a backstop.
        pybullet.resetBaseVelocity(
            self._pepper.robot_model, [0, 0, 0], [0, 0, 0],
            physicsClientId=self._pepper.physics_client)

    def getRobotPosition(self, useSensors=True):
        # qibullet's getPosition returns (x, y, theta); NAOqi callers expect a list, and `useSensors` has no sim equivalent.
        return list(self._pepper.getPosition())

    def getAngles(self, names, useSensors=True):
        # qibullet returns a scalar for a single name and NAOqi always returns a list, so wrap it; `useSensors` is ignored.
        result = self._pepper.getAnglesPosition(names)
        if isinstance(result, list):
            return result
        return [result]

    def setAngles(self, names, angles, fraction_max_speed):
        self._pepper.setAngles(names, angles, fraction_max_speed)

    def angleInterpolation(self, names, angles, durations, isAbsolute=True):
        # qibullet has no time-curve interpolation; one setAngles at 0.5 speed, discarding durations and isAbsolute.
        self._pepper.setAngles(names, angles, 0.5)

    def wait(self, task_id, timeout_ms=None):
        return self._tasks.wait(task_id, timeout_ms)

    # --- Stubs (no qibullet equivalent) ---

    @stub()
    def wakeUp(self):
        return None

    @stub()
    def rest(self):
        return None

    @stub()
    def robotIsWakeUp(self):
        return True

    @stub()
    def setStiffnesses(self, *args, **kwargs):
        return None

    @stub()
    def setBreathConfig(self, *args, **kwargs):
        return None

    @stub()
    def setBreathEnabled(self, *args, **kwargs):
        return None

    @stub()
    def setExternalCollisionProtectionEnabled(self, *args, **kwargs):
        return None

    @stub()
    def getRobotConfig(self):
        return []
