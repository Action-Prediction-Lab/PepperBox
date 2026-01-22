import sys
import os

# Add the bridge folder to path so we can import modules from it
# We are in tests/, so bridge is in ../py3-naoqi-bridge
bridge_path = os.path.join(os.path.dirname(__file__), "..", "py3-naoqi-bridge")
sys.path.append(bridge_path)

from naoqi_proxy import NaoqiClient
import math
import time

def test_motion():
    print("Connecting to PepperBox Shim...")
    client = NaoqiClient() # defaults to localhost:5000
    
    print("Commanding: Rotate Left (Z-axis)...")
    # ALMotion.move(x, y, theta) -> Velocity control
    # Spin at 0.5 rad/s
    client.ALMotion.move(0.0, 0.0, 0.5)
    
    print("Wait 3 seconds...")
    time.sleep(3)
    
    print("Commanding: Stop")
    client.ALMotion.move(0.0, 0.0, 0.0)
    
    print("Commanding: Move Head Pitch...")
    # Only if your shim implements 'setAngles' or similar for joints
    # client.ALMotion.setStiffnesses("Head", 1.0)
    # client.ALMotion.setAngles("HeadPitch", 0.5, 0.1)
    
    print("Motion Test Complete.")

if __name__ == "__main__":
    test_motion()
