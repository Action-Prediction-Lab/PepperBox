# py3-naoqi-bridge/audio_publisher.py (Python 2)
"""NAOqi ALAudioDevice -> ZMQ PUB :5563.

processRemote only enqueues because ZMQ sockets are not thread-safe and the publisher thread owns the socket; mirrors ros-naoqi naoqi_sensors_py/naoqi_microphone.py.
"""
from __future__ import print_function
import os
import socket
import sys
import threading
import time
import Queue  # Py2
import zmq

from robot_address import callback_ip


CHUNK_PUB_PORT = 5563
EXPECTED_CHUNK_BYTES = 5440  # 170 ms at 16 kHz mono int16
CALLBACK_WATCHDOG_S = 15.0


class PublisherThread(threading.Thread):
    def __init__(self, port=CHUNK_PUB_PORT):
        threading.Thread.__init__(self)
        self.daemon = True
        self.queue = Queue.Queue(maxsize=64)
        self._stop = threading.Event()
        ctx = zmq.Context.instance()
        self._sock = ctx.socket(zmq.PUB)
        self._sock.bind("tcp://*:%d" % port)

    def enqueue(self, chunk_bytes):
        try:
            self.queue.put_nowait(chunk_bytes)
        except Queue.Full:
            # Drop rather than block the NAOqi dispatcher.
            sys.stderr.write("audio_publisher: queue full; dropped one chunk\n")

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            try:
                chunk = self.queue.get(timeout=0.1)
            except Queue.Empty:
                continue
            try:
                self._sock.send(chunk)
            except zmq.ZMQError as e:
                sys.stderr.write("audio_publisher: zmq send error: %s\n" % e)
        self._sock.close()


# NAOqi imports - guarded so unit tests can load the module without naoqi installed.
try:
    from naoqi import ALModule, ALProxy, ALBroker
    _NAOQI_AVAILABLE = True
except ImportError:
    _NAOQI_AVAILABLE = False


# Strong module-level reference: NaoQiModule keeps weakrefs, so a local-only one is GC'd and processRemote silently no-ops; the name MUST match the ALModule name string.
PepperAudioPub = None


class AudioPublisherModule(ALModule if _NAOQI_AVAILABLE else object):
    """ALModule that receives audio callbacks and forwards to the publisher thread."""

    def __init__(self, module_name, publisher, ip, port, bind_ip="0.0.0.0"):
        if not _NAOQI_AVAILABLE:
            raise RuntimeError("naoqi is not importable; AudioPublisherModule cannot run.")
        self._broker = ALBroker("pepperAudioBroker", bind_ip, 0, ip, port)
        ALModule.__init__(self, module_name)
        self._publisher = publisher
        self._first_callback_checked = False
        self._audio_proxy = ALProxy("ALAudioDevice", ip, port)
        self._audio_proxy.setClientPreferences(self.getName(), 16000, 3, 0)
        self._audio_proxy.subscribe(self.getName())

    def processRemote(self, nbOfChannels, nbOfSamplesByChannel, timeStamp, inputBuffer):
        """NAOqi audio callback; ALModule.autoBind registers only methods with a
        non-empty __doc__, so emptying this docstring stops all audio delivery."""
        self._first_callback_checked = True
        expected = nbOfChannels * nbOfSamplesByChannel * 2
        if len(inputBuffer) != expected:
            try:
                inputBuffer = self._getInputBuffer()
            except Exception:
                sys.stderr.write("audio_publisher: buffer length mismatch and fallback failed\n")
                return

        self._publisher.enqueue(inputBuffer)

    def shutdown(self):
        try:
            self._audio_proxy.unsubscribe(self.getName())
        except Exception:
            pass
        self._broker.shutdown()


def _probe_reachable(ip, port, timeout_s=3.0):
    """Raw TCP fast-fail probe before the ALBroker is built; an ALProxy here would open a default broker session that later ALProxy calls bind to, breaking callback routing on hardware."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout_s)
    try:
        s.connect((ip, port))
        return True
    except Exception:
        return False
    finally:
        s.close()


def main():
    if not _NAOQI_AVAILABLE:
        sys.stderr.write("audio_publisher: naoqi not importable; exiting.\n")
        return 2

    naoqi_ip = os.environ.get("NAOQI_IP", "127.0.0.1")
    naoqi_port = int(os.environ.get("NAOQI_PORT", "9559"))

    if not _probe_reachable(naoqi_ip, naoqi_port, timeout_s=3.0):
        sys.stderr.write("audio_publisher: NAOqi unreachable at %s:%d\n" % (naoqi_ip, naoqi_port))
        return 3

    publisher = PublisherThread()
    publisher.start()

    bind_ip = callback_ip(naoqi_ip, naoqi_port)
    sys.stderr.write("audio_publisher: broker bind_ip=%s target=%s:%d\n" % (bind_ip, naoqi_ip, naoqi_port))

    global PepperAudioPub
    PepperAudioPub = AudioPublisherModule("PepperAudioPub", publisher, naoqi_ip, naoqi_port, bind_ip=bind_ip)

    # Routability watchdog: if no callback arrives before timeout, exit non-zero.
    time.sleep(CALLBACK_WATCHDOG_S)
    if publisher.queue.empty() and not PepperAudioPub._first_callback_checked:
        sys.stderr.write("audio_publisher: no callbacks received; broker unreachable from robot\n")
        PepperAudioPub.shutdown()
        publisher.stop()
        publisher.join(timeout=2.0)
        return 4

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        PepperAudioPub.shutdown()
        publisher.stop()
        publisher.join(timeout=2.0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
