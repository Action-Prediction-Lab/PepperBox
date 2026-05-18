"""ALMotion adapter. Overrides where qibullet's API differs from NAOqi;
stubs for NAOqi methods qibullet doesn't model."""

from qibullet.base_controller import PepperBaseController

from .base import GenericAdapter, stub


class ALMotionAdapter(GenericAdapter):

    # --- Overrides ---

    def move(self, x, y, theta):
        self._pepper.move(float(x), float(y), float(theta))

    def moveToward(self, x, y, theta):
        # NAOqi: normalized velocity in [-1, 1]. Translate to qibullet's
        # absolute m/s and rad/s using the base controller's max constants.
        self._pepper.move(
            float(x) * PepperBaseController.MAX_LINEAR_VELOCITY,
            float(y) * PepperBaseController.MAX_LINEAR_VELOCITY,
            float(theta) * PepperBaseController.MAX_ANGULAR_VELOCITY,
        )

    def moveTo(self, x, y, theta):
        # NAOqi's moveTo is async-by-default; qibullet's is synchronous.
        # Force async to match NAOqi semantics.
        self._pepper.moveTo(float(x), float(y), float(theta), _async=True)

    def stopMove(self):
        # qibullet's stopMove only cancels async moveTo. Compose with
        # move(0,0,0) to zero the velocity that move() may have set.
        self._pepper.stopMove()
        self._pepper.move(0, 0, 0)

    def getRobotPosition(self, useSensors=True):
        # qibullet's getPosition returns (x, y, theta). NAOqi callers
        # expect a list. `useSensors` has no sim equivalent and is ignored.
        return list(self._pepper.getPosition())

    def getAngles(self, names, useSensors=True):
        # qibullet returns a scalar for single-name requests, list otherwise.
        # NAOqi's getAngles always returns a list. Wrap scalar.
        result = self._pepper.getAnglesPosition(names)
        if isinstance(result, list):
            return result
        return [result]

    def setAngles(self, names, angles, fraction_max_speed):
        self._pepper.setAngles(names, angles, fraction_max_speed)

    def angleInterpolation(self, names, angles, durations, isAbsolute=True):
        # qibullet has no time-curve interpolation. Run a single setAngles
        # at moderate speed; durations and isAbsolute are ignored.
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

    @stub(default=True)
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

    @stub(default=[])
    def getRobotConfig(self):
        return []
