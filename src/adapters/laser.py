"""ALLaser adapter: a PepperBox-invented NAOqi module name mapped to qibullet's laser debug lines."""

from .base import GenericAdapter


class ALLaserAdapter(GenericAdapter):

    def show(self, state):
        self._pepper.showLaser(bool(state))
        return True
