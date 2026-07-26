import time
import unittest
import zmq

from audio_publisher import PublisherThread, EXPECTED_CHUNK_BYTES


class TestPublisherThread(unittest.TestCase):
    def test_chunks_forwarded(self):
        t = PublisherThread(port=15563)
        t.start()
        time.sleep(0.1)

        ctx = zmq.Context.instance()
        sub = ctx.socket(zmq.SUB)
        sub.connect("tcp://localhost:15563")
        sub.setsockopt(zmq.SUBSCRIBE, b"")
        time.sleep(0.1)

        chunk = b"\x00\x00" * (EXPECTED_CHUNK_BYTES // 2)
        t.enqueue(chunk)

        sub.setsockopt(zmq.RCVTIMEO, 500)
        got = sub.recv()
        self.assertEqual(len(got), EXPECTED_CHUNK_BYTES)
        t.stop()
        t.join(timeout=2.0)


import threading
import time

from audio_publisher import AudioPublisherModule, _NAOQI_AVAILABLE


class _RecordingPublisher(object):
    """Stand-in for PublisherThread that just records what it receives."""
    def __init__(self):
        self.received = []
    def enqueue(self, chunk_bytes):
        self.received.append(chunk_bytes)


def _make_module_without_init():
    """Build an AudioPublisherModule instance bypassing NAOqi-calling __init__."""
    mod = AudioPublisherModule.__new__(AudioPublisherModule)
    mod._publisher = _RecordingPublisher()
    mod._first_callback_checked = False
    return mod


class TestProcessRemote(unittest.TestCase):
    def test_normal_callback_enqueues_buffer(self):
        mod = _make_module_without_init()
        buf = b"\x01\x00" * 2720  # 5440 bytes, channels=1, samples=2720
        mod.processRemote(1, 2720, (123, 456), buf)
        self.assertEqual(mod._publisher.received, [buf])
        self.assertTrue(mod._first_callback_checked)

    def test_length_mismatch_triggers_fallback(self):
        """If inputBuffer length doesn't match expected, fall back to _getInputBuffer."""
        mod = _make_module_without_init()

        fallback_buf = b"\xff\xff" * 2720
        mod._getInputBuffer = lambda: fallback_buf

        bad_buf = b"\x00" * 100  # way short
        mod.processRemote(1, 2720, (0, 0), bad_buf)
        self.assertEqual(mod._publisher.received, [fallback_buf])

    def test_length_mismatch_fallback_failure_drops_chunk(self):
        """If fallback itself raises, processRemote drops silently (logs to stderr)."""
        mod = _make_module_without_init()

        def boom():
            raise RuntimeError("no fallback buffer available")
        mod._getInputBuffer = boom

        bad_buf = b"\x00" * 100
        mod.processRemote(1, 2720, (0, 0), bad_buf)
        self.assertEqual(mod._publisher.received, [])


if __name__ == "__main__":
    unittest.main()
