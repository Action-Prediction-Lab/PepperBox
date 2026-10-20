"""Tests for the bridge services' stop signal handling."""
import os
import signal
import unittest

from stop_signals import catch_stop_signals


class StopSignalTests(unittest.TestCase):
    def setUp(self):
        self.saved = signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT)

    def tearDown(self):
        signal.signal(signal.SIGTERM, self.saved[0])
        signal.signal(signal.SIGINT, self.saved[1])

    def test_the_first_stop_signal_raises_and_later_ones_are_ignored(self):
        """SIGTERM raises KeyboardInterrupt once and leaves both stop signals ignored."""
        catch_stop_signals()
        with self.assertRaises(KeyboardInterrupt):
            os.kill(os.getpid(), signal.SIGTERM)
        self.assertEqual((signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT)), (signal.SIG_IGN, signal.SIG_IGN))
        os.kill(os.getpid(), signal.SIGINT)
        os.kill(os.getpid(), signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
