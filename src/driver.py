from qibullet import SimulationManager
from qibullet import PepperVirtual
import time

class QiBulletDriver:
    def __init__(self, gui=True):
        self.simulation_manager = SimulationManager()
        # Launch simulation
        self.client = self.simulation_manager.launchSimulation(gui=gui)
        # Spawn Pepper
        print("Spawning Pepper...")
        self.pepper = self.simulation_manager.spawnPepper(
            self.client,
            spawn_ground_plane=True
        )
        print("Pepper spawned.")
        
        # Subscribe to Lasers to simulate Sonar
        self.pepper.subscribeLaser()
        print("Lasers subscribed (simulating Sonar).")

    def start_motion(self, x, y, theta):
        # Explicit naming to clear up confusion
        self.pepper.move(x, y, theta)

    def move(self, x, y, theta):
        self.pepper.move(x, y, theta)

    def stop_motion(self):
        self.pepper.move(0.0, 0.0, 0.0)

    def set_posture(self, posture_name, speed=0.5):
        # qibullet supports: Stand, StandInit, StandZero, Crouch, Sit, SitRelax
        # Naoqi might send others, but we map strictly or pass through
        print(f"[QiBullet] Setting Posture: {posture_name}")
        self.pepper.goToPosture(posture_name, speed)

    def get_front_sonar(self):
        # Proxy: Use minimum distance from Front Laser
        # Returns float in meters
        lasers = self.pepper.getFrontLaserValue()
        if not lasers:
            return 3.0 # Max range if empty
        return min(lasers)

    def get_back_sonar(self):
        # Proxy: Use minimum distance from Left/Right lasers (which cover rear quadrants)
        left = self.pepper.getLeftLaserValue()
        right = self.pepper.getRightLaserValue()
        combined = left + right
        if not combined:
            return 3.0
        return min(combined)

    def get_front_laser(self):
        # Returns the full list of float values (rays)
        return self.pepper.getFrontLaserValue()

    def show_lasers(self, state=True):
        # Toggles the red/green debug lines in the PyBullet GUI
        self.pepper.showLaser(state)

    def get_position(self):
        # Returns [x, y, theta] in World Frame
        # qibullet getPosition() returns x, y, theta
        return self.pepper.getPosition()

    def say(self, text):
        print(f"[QiBullet] ROBOT SAYS: {text}")
        
    def step(self):
        # PyBullet steps automatically in GUI mode usually, 
        # but we can force step if needed or just keep thread alive.
        time.sleep(0.1)
        return True

    def stop(self):
        self.simulation_manager.stopSimulation(self.client)
