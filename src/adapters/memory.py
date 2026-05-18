"""ALMemory adapter. Key-routed getData translates NAOqi's stringly-typed
sensor lookups to qibullet's laser API. Most ALMemory operations have no
qibullet equivalent and stub to None or the closest sensible value."""

from .base import GenericAdapter, stub

_SONAR_FRONT = "Device/SubDeviceList/Platform/Front/Sonar/Sensor/Value"
_SONAR_BACK = "Device/SubDeviceList/Platform/Back/Sonar/Sensor/Value"
_LASER_FRONT = "Device/SubDeviceList/Platform/Laser/Front/Sensor/Value"
_LANDMARK = "LandmarkDetected"
_MAX_SONAR_RANGE = 3.0  # meters 


class ALMemoryAdapter(GenericAdapter):

    def getData(self, key, *_rest):
        # NAOqi's ALMemory.getData accepts an optional 2nd arg (timeout/format).
        # Capture it as *_rest and ignore.
        if key == _SONAR_FRONT:
            return self._min_laser(self._pepper.getFrontLaserValue())
        if key == _SONAR_BACK:
            left = self._pepper.getLeftLaserValue() or []
            right = self._pepper.getRightLaserValue() or []
            return self._min_laser(list(left) + list(right))
        if key == _LASER_FRONT:
            return self._pepper.getFrontLaserValue()
        if key == _LANDMARK:
            # Empty detection
            return [0, [], 0]
        # Unknown key
        return None

    def getListData(self, keys):
        return [self.getData(k) for k in keys]

    @stub()
    def insertData(self, *args, **kwargs):
        return None

    @staticmethod
    def _min_laser(values):
        if not values:
            return _MAX_SONAR_RANGE
        return min(values)
