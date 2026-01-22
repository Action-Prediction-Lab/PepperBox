import sys
import os
import time

# Add the bridge folder to path so we can import modules from it
bridge_path = os.path.join(os.path.dirname(__file__), "..", "py3-naoqi-bridge")
sys.path.append(bridge_path)

from naoqi_proxy import NaoqiClient

def test_sonar():
    print("Connecting to PepperBox Shim (Sonar Test)...")
    client = NaoqiClient()
    
    print("Reading Sonar Values...")
    # Front Sonar
    front = client.ALMemory.getData("Device/SubDeviceList/Platform/Front/Sonar/Sensor/Value")
    print(f"Front Sonar: {front} meters")
    
    # Back Sonar
    back = client.ALMemory.getData("Device/SubDeviceList/Platform/Back/Sonar/Sensor/Value")
    print(f"Back Sonar:  {back} meters")
    
    if front is not None and back is not None:
        print("\nSUCCESS: Sonar values received (simulated via Laser).")
    else:
        print("\nFAILURE: One or more sonar values were None.")

if __name__ == "__main__":
    test_sonar()
