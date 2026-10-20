"""Tests for callback_ip."""
import os
import unittest

from robot_address import callback_ip


class CallbackIpTests(unittest.TestCase):
    def setUp(self):
        self.saved = os.environ.pop("NAOQI_CALLBACK_IP", None)

    def tearDown(self):
        os.environ.pop("NAOQI_CALLBACK_IP", None)
        if self.saved is not None:
            os.environ["NAOQI_CALLBACK_IP"] = self.saved

    def test_the_override_is_used_when_set(self):
        """callback_ip returns NAOQI_CALLBACK_IP when it is set."""
        os.environ["NAOQI_CALLBACK_IP"] = "172.17.0.1"
        self.assertEqual(callback_ip("127.0.0.2", 9559), "172.17.0.1")

    def test_without_the_override_the_route_to_the_robot_decides(self):
        """Without NAOQI_CALLBACK_IP, callback_ip returns the local address on the route to the robot."""
        self.assertEqual(callback_ip("127.0.0.2", 9559), "127.0.0.1")

    def test_an_empty_override_is_ignored(self):
        """callback_ip ignores an empty NAOQI_CALLBACK_IP."""
        os.environ["NAOQI_CALLBACK_IP"] = ""
        self.assertEqual(callback_ip("127.0.0.2", 9559), "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
