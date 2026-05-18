"""This is the qibullet sim lifecycle owner.

Holds the simulation and the Pepper instance the adapters dispatch against.
Adapters call into `self.pepper` directly."""

from qibullet import SimulationManager


class QiBulletDriver:

    def __init__(self, gui=True):
        self.simulation_manager = SimulationManager()
        self.client = self.simulation_manager.launchSimulation(gui=gui)
        print("Spawning Pepper...")
        self.pepper = self.simulation_manager.spawnPepper(
            self.client, spawn_ground_plane=True
        )
        print("Pepper spawned.")
        self.pepper.subscribeLaser()
        print("Lasers subscribed (simulating Sonar).")

    def stop(self):
        """Tear down the simulation."""
        self.simulation_manager.stopSimulation(self.client)
