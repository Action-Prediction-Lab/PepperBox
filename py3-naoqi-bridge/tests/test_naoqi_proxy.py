import unittest
import os
import time
from ..naoqi_proxy import NaoqiClient, NaoqiProxyError

# Assuming the shim server is running at localhost:5000
# And the robot.env is configured correctly for the shim server

class TestNaoqiProxy(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Initialize NaoqiClient once for all tests
        cls.client = NaoqiClient()

    def test_01_text_to_speech_say(self):
        """Test ALTextToSpeech.say method."""
        print("\n--- Test: ALTextToSpeech.say ---")
        try:
            # This will send a command to the robot, no direct return value to assert
            self.client.ALTextToSpeech.say("Hello from unittest")
            print("ALTextToSpeech.say successful.")
            self.assertTrue(True) # If no exception, consider it a success
        except NaoqiProxyError as e:
            self.fail(f"ALTextToSpeech.say failed with NaoqiProxyError: {e}")
        except Exception as e:
            self.fail(f"ALTextToSpeech.say failed with unexpected error: {e}")

    def test_02_motion_get_robot_config(self):
        """Test ALMotion.getRobotConfig method and its return value."""
        print("\n--- Test: ALMotion.getRobotConfig ---")
        try:
            config = self.client.ALMotion.getRobotConfig()
            print(f"ALMotion.getRobotConfig returned: {config}")
            self.assertIsInstance(config, list)
            # Further assertions could be made if the expected config structure is known
        except NaoqiProxyError as e:
            self.fail(f"ALMotion.getRobotConfig failed with NaoqiProxyError: {e}")
        except Exception as e:
            self.fail(f"ALMotion.getRobotConfig failed with unexpected error: {e}")

    def test_03_error_for_non_existent_method(self):
        """Test that calling a non-existent method raises NaoqiProxyError."""
        print("\n--- Test: Non-existent method ---")
        with self.assertRaises(NaoqiProxyError) as cm:
            self.client.ALTextToSpeech.nonExistentMethod("test")
        print(f"Caught expected error: {cm.exception}")
        self.assertIn("Can't find method: nonExistentMethod", str(cm.exception))

    def test_04_error_for_non_existent_module(self):
        """Test that calling a method on a non-existent module raises NaoqiProxyError."""
        print("\n--- Test: Non-existent module ---")
        with self.assertRaises(NaoqiProxyError) as cm:
            self.client.ALNonExistentModule.someMethod("test")
        print(f"Caught expected error: {cm.exception}")
        self.assertIn("Can't find service: ALNonExistentModule", str(cm.exception))

    def test_05_argument_passing(self):
        """Test passing various argument types to a method."""
        print("\n--- Test: Argument Passing ---")
        try:
            # Assuming ALMemory.insertData can take various types
            self.client.ALMemory.insertData("testKeyString", "stringValue")
            self.client.ALMemory.insertData("testKeyInt", 123)
            self.client.ALMemory.insertData("testKeyFloat", 123.45)
            self.client.ALMemory.insertData("testKeyBool", True)
            self.client.ALMemory.insertData("testKeyList", [1, "two", False])
            self.client.ALMemory.insertData("testKeyDict", {"a": 1, "b": "two"})
            print("ALMemory.insertData with various argument types successful.")
            self.assertTrue(True)
        except NaoqiProxyError as e:
            self.fail(f"Argument passing test failed with NaoqiProxyError: {e}")
        except Exception as e:
            self.fail(f"Argument passing test failed with unexpected error: {e}")

    # def test_06_get_data_from_memory(self):
    #     """Test retrieving data from ALMemory."""
    #     print("\n--- Test: Get Data from Memory ---")
    #     try:
    #         # Retrieve data inserted in the previous test
    #         string_val = self.client.ALMemory.getData("testKeyString")
    #         self.assertEqual(string_val, "stringValue")

    #         int_val = self.client.ALMemory.getData("testKeyInt")
    #         self.assertEqual(int_val, 123)

    #         list_val = self.client.ALMemory.getData("testKeyList")
    #         self.assertEqual(list_val, [1, "two", False])

    #         print("ALMemory.getData successful.")
    #     except NaoqiProxyError as e:
    #         self.fail(f"ALMemory.getData test failed with NaoqiProxyError: {e}")
    #     except Exception as e:
    #         self.fail(f"ALMemory.getData test failed with unexpected error: {e}")

if __name__ == '__main__':
    unittest.main()
