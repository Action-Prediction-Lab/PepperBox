"""Sim-side joint state publisher.

Mirrors the wire format of `py3-naoqi-bridge/state_service.py` so one Python 3 client works against sim and robot.
"""

import struct
import sys
import threading
import time

import zmq


class JointPublisher(threading.Thread):
    """50Hz PUB of HeadYaw/HeadPitch on :5560 topic 'joints'."""

    def __init__(self, pepper, rate_hz=50.0, port=5560):
        super(JointPublisher, self).__init__()
        self.pepper = pepper
        self.dt = 1.0 / rate_hz
        self.port = port
        self.daemon = True

    def run(self):
        ctx = zmq.Context()
        sock = ctx.socket(zmq.PUB)
        sock.bind("tcp://*:{}".format(self.port))
        print("[JointPublisher] Bound ZMQ PUB on tcp://*:{}".format(self.port))
        while True:
            loop_start = time.time()
            try:
                angles = self.pepper.getAnglesPosition(["HeadYaw", "HeadPitch"])
                if angles and len(angles) == 2:
                    payload = struct.pack("dff", loop_start, angles[0], angles[1])
                    sock.send_multipart([b"joints", payload])
            except Exception as e:
                sys.stderr.write("[JointPublisher] Error: {}\n".format(e))
            elapsed = time.time() - loop_start
            if elapsed < self.dt:
                time.sleep(self.dt - elapsed)
