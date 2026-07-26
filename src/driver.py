"""qibullet sim lifecycle owner: holds the simulation and the `pepper` instance adapters dispatch against."""

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
