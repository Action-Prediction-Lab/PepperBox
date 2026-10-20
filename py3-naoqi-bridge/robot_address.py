# py3-naoqi-bridge/robot_address.py (Python 2)
"""Finds the host address that NAOqi uses to reach services on this host."""
import os
import socket


def callback_ip(naoqi_ip, naoqi_port):
    """Returns NAOQI_CALLBACK_IP if it is set, else the local address on the route to the robot."""
    override = os.environ.get("NAOQI_CALLBACK_IP")
    if override:
        return override
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((naoqi_ip, naoqi_port))
        return s.getsockname()[0]
    except Exception:
        return "0.0.0.0"
    finally:
        s.close()
