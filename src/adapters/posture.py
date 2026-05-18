"""ALRobotPosture adapter. Direct passthrough to qibullet's goToPosture,
which returns False for postures qibullet doesn't model (Sit, SitRelax,
LyingBelly, LyingBack)."""

from .base import GenericAdapter


class ALRobotPostureAdapter(GenericAdapter):

    def goToPosture(self, name, speed):
        return self._pepper.goToPosture(name, speed)
