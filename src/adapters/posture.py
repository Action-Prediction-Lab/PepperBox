"""ALRobotPosture adapter: passthrough to qibullet's goToPosture, which returns False for Sit, SitRelax, LyingBelly and LyingBack."""

from .base import GenericAdapter


class ALRobotPostureAdapter(GenericAdapter):

    def goToPosture(self, name, speed):
        return self._pepper.goToPosture(name, speed)
