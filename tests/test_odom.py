import sys
import os
import time

# Add the bridge folder to path so we can import modules from it
bridge_path = os.path.join(os.path.dirname(__file__), "..", "py3-naoqi-bridge")
sys.path.append(bridge_path)

from naoqi_proxy import NaoqiClient

def test_odom_vis():
    print("Connecting to PepperBox Shim (Odom & Vis Test)...")
    client = NaoqiClient()
    
    print("\n1. Enabling Laser Visualization (Check Simulator Window!)...")
    # Using our custom ALLaser module
    client.ALLaser.show(True)
    
    print("2. Monitoring Odometry while rotating...")
    # Start rotating
    client.ALMotion.move(0.0, 0.0, 0.5)
    
    try:
        for i in range(10):
            # getRobotPosition(useSensors) -> [x, y, theta]
            pos = client.ALMotion.getRobotPosition(True)
            print(f"Odom: X={pos[0]:.3f}, Y={pos[1]:.3f}, Theta={pos[2]:.3f}")
            time.sleep(0.5)
            
    finally:
        print("Stopping...")
        client.ALMotion.stopMove()
        # Optionally turn off lasers
        # client.ALLaser.show(False)

if __name__ == "__main__":
    test_odom_vis()
