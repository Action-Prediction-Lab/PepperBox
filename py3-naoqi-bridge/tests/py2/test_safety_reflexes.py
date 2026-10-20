"""Tests for applying NAOqi's safety reflexes from config."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from StringIO import StringIO

from safety_reflexes import apply_reflexes, back_on, read_reflexes, switch_back_on


class FakeMotion(object):
    """Fake ALMotion whose external collision protection reads back stale for a number of reads after each change."""

    def __init__(self, stale_reads=0, refuse=False, never_settles=False):
        self.state = {}
        self.pending = {}
        self.stale_reads = stale_reads
        self.refuse = refuse
        self.never_settles = never_settles
        self.calls = []

    def setExternalCollisionProtectionEnabled(self, name, enabled):
        self.calls.append((name, enabled))
        if self.refuse:
            raise RuntimeError("You have attempted to disactivate the \"Move\" external collision protection without first enabling the disactivation of this safety reflex.")
        self.pending[name] = [enabled, self.stale_reads]

    def getExternalCollisionProtectionEnabled(self, name):
        if name in self.pending and not self.never_settles:
            value, left = self.pending[name]
            if left <= 0:
                self.state[name] = value
                del self.pending[name]
            else:
                self.pending[name][1] = left - 1
        return self.state.get(name, True)


TIMING = {"poll_interval_s": 0.0, "wait_limit_s": 1.0}


class ApplyTests(unittest.TestCase):
    def test_each_chain_is_set_and_reads_back(self):
        """apply_reflexes sets each chain once and reads it until the fake settles it."""
        motion = FakeMotion(stale_reads=3)
        apply_reflexes(motion, {"ExternalCollisionProtection": {"Arms": False, "Move": False}}, **TIMING)
        self.assertEqual((motion.state, motion.pending), ({"Arms": False, "Move": False}, {}))
        self.assertEqual(motion.calls, [("Arms", False), ("Move", False)])

    def test_stale_reads_are_waited_out(self):
        """apply_reflexes accepts a setting that reads back stale for a few reads once two reads in a row return it, without sending it again."""
        motion = FakeMotion(stale_reads=3)
        apply_reflexes(motion, {"ExternalCollisionProtection": {"Arms": False}}, **TIMING)
        self.assertIs(motion.getExternalCollisionProtectionEnabled("Arms"), False)
        self.assertEqual(motion.calls, [("Arms", False)])

    def test_a_setting_that_never_settles_raises(self):
        motion = FakeMotion(never_settles=True)
        with self.assertRaises(RuntimeError):
            apply_reflexes(motion, {"ExternalCollisionProtection": {"Arms": False}}, poll_interval_s=0.0, wait_limit_s=0.05)

    def test_a_refused_setting_raises(self):
        """apply_reflexes raises when NAOqi refuses a setting."""
        with self.assertRaises(RuntimeError):
            apply_reflexes(FakeMotion(refuse=True), {"ExternalCollisionProtection": {"All": False}}, **TIMING)


class SwitchBackOnTests(unittest.TestCase):
    def test_only_the_chains_switched_off_are_switched_back_on(self):
        self.assertEqual(back_on({"ExternalCollisionProtection": {"Arms": False, "Move": True}}), {"ExternalCollisionProtection": {"Arms": True}})

    def test_nothing_switched_off_needs_nothing_back_on(self):
        self.assertEqual(back_on({"ExternalCollisionProtection": {"Arms": True}}), {})

    def test_switching_back_on_reads_the_protection_back(self):
        """switch_back_on sets the chain back on and reads it until the fake settles it."""
        motion = FakeMotion(stale_reads=3)
        reflexes = {"ExternalCollisionProtection": {"Arms": False}}
        apply_reflexes(motion, reflexes, **TIMING)
        stderr, sys.stderr = sys.stderr, StringIO()
        try:
            switch_back_on(motion, reflexes, TIMING)
        finally:
            sys.stderr = stderr
        self.assertEqual((motion.state, motion.pending), ({"Arms": True}, {}))
        self.assertEqual(motion.calls, [("Arms", False), ("Arms", True)])


class SwitchBackOnFailureTests(unittest.TestCase):
    def test_a_refused_switch_back_on_is_logged_and_does_not_raise(self):
        stderr, sys.stderr = sys.stderr, StringIO()
        try:
            switch_back_on(FakeMotion(refuse=True), {"ExternalCollisionProtection": {"Arms": False}}, TIMING)
            logged = sys.stderr.getvalue()
        finally:
            sys.stderr = stderr
        self.assertIn("safety_reflexes: cannot switch the protections back on", logged)


class ReadTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def write(self, content):
        path = os.path.join(self.dir, "safety_reflexes.json")
        with open(path, "w") as f:
            f.write(json.dumps(content))
        return path

    def shipped(self):
        return read_reflexes(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "config", "safety_reflexes.json"))

    def test_the_shipped_default_keeps_the_arm_protection_on(self):
        self.assertEqual(self.shipped()[1], {"ExternalCollisionProtection": {"Arms": True}})

    def test_the_shipped_default_gives_positive_read_back_timing(self):
        timing = self.shipped()[0]
        self.assertTrue(all(timing[key] > 0 for key in ("poll_interval_s", "wait_limit_s")))

    def test_the_timing_comes_apart_from_the_reflexes(self):
        timing, reflexes = read_reflexes(self.write(dict(TIMING, ExternalCollisionProtection={"Arms": False})))
        self.assertEqual((timing, reflexes), (TIMING, {"ExternalCollisionProtection": {"Arms": False}}))

    def test_a_missing_timing_value_is_rejected(self):
        with self.assertRaises(ValueError):
            read_reflexes(self.write({"poll_interval_s": 0.5, "ExternalCollisionProtection": {"Arms": False}}))

    def test_an_unknown_reflex_is_rejected(self):
        with self.assertRaises(ValueError):
            read_reflexes(self.write(dict(TIMING, CollisionAvoidance={"Arms": False})))

    def test_a_value_that_is_not_true_or_false_is_rejected(self):
        with self.assertRaises(ValueError):
            read_reflexes(self.write(dict(TIMING, ExternalCollisionProtection={"Arms": "off"})))


if __name__ == "__main__":
    unittest.main()
