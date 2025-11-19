# test_motion.py
import os
import sys

# Add the parent directory to the path to find the 'naoqi_proxy' module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from naoqi_proxy import NaoqiClient, NaoqiProxyError

# --- Connection Settings ---
# The shim server runs on localhost inside the container.
# The Robot IP is configured in the shim_server's environment.
NAOQI_SHIM_IP = "127.0.0.1"
NAOQI_SHIM_PORT = 5000

def run_test():
    """
    Connects to the Naoqi proxy and attempts to call methods
    that previously failed with nested arguments.
    """
    print("--- Starting Naoqi proxy test ---")
    print("Connecting to Shim Server: {}:{}".format(NAOQI_SHIM_IP, NAOQI_SHIM_PORT))
    print("Target Robot IP is configured in the shim server's environment (NAOQI_IP).")
    
    print("\nReminder: Make sure the shim_server.py is running in a separate terminal:")
    print("~/.pyenv/versions/2.7.18/bin/python ~/py3-naoqi-bridge/shim_server.py\n")

    try:
        client = NaoqiClient(host=NAOQI_SHIM_IP, port=NAOQI_SHIM_PORT)
        print("Successfully connected to proxy.")

        # --- Test 1: ALMotion.setBreathConfig ---
        # This call uses a list of lists, which previously failed.
        breath_config = [
            ['Bpm', 15.0],
            ['Amplitude', 0.9]
        ]
        print("\nAttempting to call ALMotion.setBreathConfig with: {}".format(breath_config))
        client.ALMotion.setBreathConfig(breath_config)
        print("ALMotion.setBreathConfig call succeeded.")

        # --- Test 2: ALMotion.setAngles ---
        # This call uses a list of joint names (strings).
        joint_names = ["RShoulderPitch", "RShoulderRoll"]
        angles = [0.5, 0.5]
        speed = 0.1
        print("\nAttempting to call ALMotion.setAngles with names: {} and angles: {}".format(joint_names, angles))
        client.ALMotion.setAngles(joint_names, angles, speed)
        print("ALMotion.setAngles call succeeded.")

        print("\nAll tests passed successfully!")

    except NaoqiProxyError as e:
        print("\nTest failed with NaoqiProxyError:")
        print("   This likely means the shim server is running but encountered an error.")
        print("   Error details: {}".format(e))
    except ImportError as e:
        print("\nTest failed with ImportError:")
        print("   Could not import NaoqiClient. Make sure you are running this script correctly.")
        print("   Error details: {}".format(e))
    except Exception as e:
        print("\nAn unexpected error occurred:")
        print("   This might be a connection issue. Is the shim_server.py running?")
        print("   Error details: {}".format(e))

if __name__ == "__main__":
    run_test()
