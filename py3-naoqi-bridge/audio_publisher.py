# py3-naoqi-bridge/audio_publisher.py (Python 2)
"""NAOqi ALAudioDevice -> ZMQ PUB :5563.

Subclass of ALModule; processRemote callback runs on a NAOqi dispatcher thread
and enqueues audio buffers. A dedicated publisher thread owns the ZMQ socket
and drains the queue -- ZMQ sockets are not thread-safe, so the NAOqi thread
must never touch the socket directly.

Mirrors ros-naoqi/naoqi_bridge/naoqi_sensors_py/.../naoqi_microphone.py.
"""
from __future__ import print_function
import os
import sys
import threading
import time
import Queue  # Py2
import zmq


CHUNK_PUB_PORT = 5563
EXPECTED_CHUNK_BYTES = 5440  # 170 ms at 16 kHz mono int16


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


class AudioPublisherModule(ALModule if _NAOQI_AVAILABLE else object):
    """ALModule that receives audio callbacks and forwards to the publisher thread."""

    def __init__(self, module_name, publisher, ip, port):
        if not _NAOQI_AVAILABLE:
            raise RuntimeError("naoqi is not importable; AudioPublisherModule cannot run.")
        self._broker = ALBroker("pepperAudioBroker", "0.0.0.0", 0, ip, port)
        ALModule.__init__(self, module_name)
        self._publisher = publisher
        self._first_callback_checked = False
        self._audio_proxy = ALProxy("ALAudioDevice", ip, port)
        self._audio_proxy.setClientPreferences(self.getName(), 16000, 3, 0)
        self._audio_proxy.subscribe(self.getName())

    def processRemote(self, nbOfChannels, nbOfSamplesByChannel, timeStamp, inputBuffer):
        if not self._first_callback_checked:
            assert nbOfChannels == 1, \
                "Expected single-channel audio (FRONTCHANNEL=3); got %d channels" % nbOfChannels
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


def _construct_with_timeout(ip, port, timeout_s=5.0):
    """Call ALProxy(ALAudioDevice, ...) inside a thread with a bounded join.

    Returns the proxy or raises RuntimeError on timeout (handles NAOqi-unreachable
    without hanging the main thread for multiple seconds).
    """
    result = [None]
    exc = [None]

    def go():
        try:
            result[0] = ALProxy("ALAudioDevice", ip, port)
        except Exception as e:
            exc[0] = e

    t = threading.Thread(target=go)
    t.daemon = True
    t.start()
    t.join(timeout_s)
    if t.is_alive():
        raise RuntimeError("ALProxy(ALAudioDevice) did not return within %.1fs" % timeout_s)
    if exc[0] is not None:
        raise exc[0]
    return result[0]


def main():
    if not _NAOQI_AVAILABLE:
        sys.stderr.write("audio_publisher: naoqi not importable; exiting.\n")
        return 2

    naoqi_ip = os.environ.get("NAOQI_IP", "127.0.0.1")
    naoqi_port = int(os.environ.get("NAOQI_PORT", "9559"))

    try:
        _ = _construct_with_timeout(naoqi_ip, naoqi_port, timeout_s=5.0)
    except Exception as e:
        sys.stderr.write("audio_publisher: ALAudioDevice unreachable: %s\n" % e)
        return 3

    publisher = PublisherThread()
    publisher.start()

    module = AudioPublisherModule("PepperAudioPub", publisher, naoqi_ip, naoqi_port)

    # Routability watchdog: if no callback arrives within 500 ms, exit non-zero.
    time.sleep(0.5)
    if publisher.queue.empty() and not module._first_callback_checked:
        sys.stderr.write("audio_publisher: no callbacks received; broker unreachable from robot\n")
        module.shutdown()
        publisher.stop()
        publisher.join(timeout=2.0)
        return 4

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        module.shutdown()
        publisher.stop()
        publisher.join(timeout=2.0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
