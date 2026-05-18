"""ALLaser adapter. PepperBox-custom NAOqi module name; maps to qibullet's
laser debug-line visualisation."""

from .base import GenericAdapter


class ALLaserAdapter(GenericAdapter):

    def show(self, state):
        self._pepper.showLaser(bool(state))
        return True
