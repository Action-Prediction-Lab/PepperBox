"""Tests for the gesture switch."""
import math
import threading
import time
import unittest

from gesture_switch import GestureSwitch, check, check_until_reachable

ARM_JOINTS = ["LShoulderPitch", "LShoulderRoll", "LElbowYaw", "LElbowRoll", "LWristYaw", "LHand",
              "RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "RWristYaw", "RHand"]
GESTURE = "animations/Stand/Gestures/Me_8"
LONG_GESTURE = "animations/Stand/Gestures/Far_3"
CONFIG = {
    "lead_s": 0.05,
    "wait_limit_s": 1.0,
    "acquire_timeout_s": 0.2,
    "poll_interval_s": 0.005,
    "gesture_speed_mm_s": 296.0,
    "retract_min_s": 0.6,
    "retract_max_s": 2.0,
    "default_duration_s": 0.3,
    "check_wait_s": 0.2,
    "check_interval_s": 0.05,
    "rest_pose": dict((name, 0.0) for name in ARM_JOINTS),
}
DURATIONS = {GESTURE: 0.4, LONG_GESTURE: 0.5}
# Shoulder-to-hand offset in mm with all arm joints at zero (elbow + wrist + hand).
REACH_X, REACH_Z = 181.2 + 150.0 + 69.5, 0.13 + 22.84 - 30.3


class FakeSignal(object):
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)
        return len(self.callbacks)

    def fire(self, *args):
        for callback in self.callbacks:
            callback(*args)


class FakeBehaviorManager(object):
    def __init__(self):
        self.behaviorStarted = FakeSignal()
        self.behaviorStopped = FakeSignal()


class FakeMotion(object):
    """Fake ALMotion that logs interpolations and breathing changes."""

    def __init__(self, log):
        self.log = log
        self.angles = dict((name, 0.0) for name in ARM_JOINTS)

    def getAngles(self, names, use_sensors):
        return [self.angles[name] for name in names]

    def angleInterpolation(self, names, targets, times, absolute):
        self.log.append(("interpolate", list(names), list(targets), list(times), absolute))

    def setBreathEnabled(self, chain, enabled):
        self.log.append(("breath", chain, enabled))


class FakeResources(object):
    """Fake ALResourceManager; acquire fails while busy is True."""

    def __init__(self, log):
        self.log = log
        self.busy = False
        self.acquired = []

    def acquireResourcesTree(self, resources, owner, callback, timeout):
        if self.busy:
            raise RuntimeError("resource busy")
        self.acquired.append(time.time())
        self.log.append(("acquire", list(resources), owner))

    def releaseResources(self, resources, owner):
        self.log.append(("release", list(resources), owner))


class FakeMemory(object):
    def __init__(self, log):
        self.log = log
        self.data = {}
        self.events = []

    def raiseEvent(self, name, value):
        self.events.append((name, value))
        self.log.append(("event", name))

    def insertData(self, key, value):
        self.data[key] = value


class FakeSpeech(object):
    """Fake ALAnimatedSpeech that passes the text to a test hook."""

    def __init__(self):
        self.calls = []
        self.deliver = lambda text: None

    def say(self, text, config):
        self.calls.append((text, config))
        self.deliver(text)


class FakeSession(object):
    def __init__(self):
        self.log = []
        self.behavior_manager = FakeBehaviorManager()
        self.motion = FakeMotion(self.log)
        self.resources = FakeResources(self.log)
        self.memory = FakeMemory(self.log)
        self.speech = FakeSpeech()

    def service(self, name):
        return {"ALBehaviorManager": self.behavior_manager, "ALMotion": self.motion, "ALResourceManager": self.resources,
                "ALMemory": self.memory, "ALAnimatedSpeech": self.speech}[name]


def wait_until(condition, limit=2.0):
    end = time.time() + limit
    while time.time() < end:
        if condition():
            return True
        time.sleep(0.005)
    return False


class SwitchTestCase(unittest.TestCase):
    def setUp(self):
        self.session = FakeSession()
        self.switch = GestureSwitch(self.session, CONFIG, DURATIONS)

    def tearDown(self):
        self.switch.on()

    def start(self, name):
        self.session.behavior_manager.behaviorStarted.fire(name)

    def first_acquire_after(self, t0, limit=2.0):
        wait_until(lambda: self.session.resources.acquired, limit)
        return self.session.resources.acquired[0] - t0 if self.session.resources.acquired else None

    def event_names(self):
        return [name for name, _ in self.session.memory.events]


class OffTimingTests(SwitchTestCase):
    def test_off_returns_while_the_gesture_is_still_moving(self):
        """off() returns before the gesture ends."""
        self.start(GESTURE)
        t = time.time()
        self.switch.off()
        self.assertLess(time.time() - t, 0.05)
        self.assertEqual(self.session.resources.acquired, [])

    def test_the_arms_are_taken_just_before_the_moving_gesture_ends(self):
        """off() takes the arms lead_s before the gesture ends."""
        t0 = time.time()
        self.start(GESTURE)
        self.switch.off()
        self.assertAlmostEqual(self.first_acquire_after(t0), 0.35, delta=0.04)

    def test_a_gesture_missing_from_the_table_uses_the_default_length(self):
        """off() uses default_duration_s for an animation that is not in the table."""
        t0 = time.time()
        self.start("animations/Stand/Gestures/NotInTheTable_1")
        self.switch.off()
        self.assertAlmostEqual(self.first_acquire_after(t0), 0.25, delta=0.04)

    def test_the_arms_are_taken_at_once_when_nothing_moves(self):
        t0 = time.time()
        self.switch.off()
        self.assertLess(self.first_acquire_after(t0), 0.04)

    def test_behaviours_outside_the_animations_package_are_not_waited_for(self):
        """off() ignores behaviours outside the animations package."""
        t0 = time.time()
        self.start("robot-page/behavior_1")
        self.switch.off()
        self.assertLess(self.first_acquire_after(t0), 0.04)

    def test_a_gesture_starting_during_the_wait_moves_the_target(self):
        """off() also waits for a gesture that starts during the wait."""
        t0 = time.time()
        self.start(GESTURE)
        self.switch.off()
        time.sleep(0.15)
        self.start(LONG_GESTURE)
        self.assertAlmostEqual(self.first_acquire_after(t0), 0.6, delta=0.05)

    def test_the_wait_gives_up_after_the_wait_limit(self):
        """If off() cannot take the arms, it raises OffTimedOut at wait_limit_s and does not retract."""
        self.session.resources.busy = True
        self.switch.off()
        self.assertTrue(wait_until(lambda: "GestureSwitch/OffTimedOut" in self.event_names()))
        self.assertNotIn("interpolate", [entry[0] for entry in self.session.log])


class CancelTests(SwitchTestCase):
    def test_on_cancels_an_off_still_waiting(self):
        """on() cancels a waiting off(), which then raises OffCancelled and does not take the arms."""
        self.start(GESTURE)
        self.switch.off()
        time.sleep(0.1)
        self.switch.on()
        time.sleep(0.4)
        self.assertEqual(self.session.resources.acquired, [])
        self.assertIn("GestureSwitch/OffCancelled", self.event_names())

    def test_on_frees_the_arms(self):
        self.switch.off()
        wait_until(lambda: "GestureSwitch/Retracted" in self.event_names())
        self.switch.on()
        self.assertEqual(self.session.log[-2:], [("release", ["Left arm", "Right arm"], "GestureSwitch"), ("event", "GestureSwitch/On")])


class RetractionTests(SwitchTestCase):
    def retraction_time(self):
        self.switch.off()
        self.assertTrue(wait_until(lambda: any(entry[0] == "interpolate" for entry in self.session.log)))
        entry = [e for e in self.session.log if e[0] == "interpolate"][0]
        self.assertEqual(len(set(entry[3])), 1)
        return entry[3][0]

    def set_shoulder_pitch(self, angle):
        self.session.motion.angles["LShoulderPitch"] = angle
        self.session.motion.angles["RShoulderPitch"] = angle

    def test_the_arms_go_to_the_rest_pose_then_breathing_starts(self):
        """The retraction moves every arm joint to its rest angle, then starts arm breathing."""
        self.switch.off()
        self.assertTrue(wait_until(lambda: ("breath", "Arms", True) in self.session.log))
        motor = [entry for entry in self.session.log if entry[0] != "event"]
        self.assertEqual([entry[0] for entry in motor[:3]], ["acquire", "interpolate", "breath"])
        _, names, targets, _, absolute = motor[1]
        self.assertEqual(sorted(names), sorted(ARM_JOINTS))
        self.assertEqual(targets, [0.0] * len(ARM_JOINTS))
        self.assertTrue(absolute)

    def test_the_retraction_moves_the_hands_at_gesture_speed(self):
        """The retraction time is the hand distance divided by the gesture speed."""
        reach = math.hypot(REACH_X, REACH_Z)
        self.set_shoulder_pitch(2 * math.asin(296.0 / (2 * reach)))
        self.assertAlmostEqual(self.retraction_time(), 1.0, places=2)

    def test_the_retraction_time_stays_within_its_bounds(self):
        """The retraction time stays between retract_min_s and retract_max_s."""
        self.assertAlmostEqual(self.retraction_time(), 0.6, places=6)
        self.assertTrue(wait_until(lambda: "GestureSwitch/Retracted" in self.event_names()))
        self.switch.on()
        del self.session.log[:]
        self.set_shoulder_pitch(math.pi)
        self.assertAlmostEqual(self.retraction_time(), 2.0, places=6)


class EventTests(SwitchTestCase):
    def test_an_off_reports_its_steps_in_order(self):
        """off() raises OffRequested with the moving gestures, then ArmsTaken, then Retracted."""
        self.start(GESTURE)
        self.switch.off()
        self.assertTrue(wait_until(lambda: "GestureSwitch/Retracted" in self.event_names()))
        self.assertEqual(self.event_names(), ["GestureSwitch/OffRequested", "GestureSwitch/ArmsTaken", "GestureSwitch/Retracted"])
        self.assertEqual(self.session.memory.events[0][1], [GESTURE])


class OffNowTests(SwitchTestCase):
    def test_off_now_returns_with_the_arms_taken_and_breathing_on(self):
        """off_now() takes the arms and starts arm breathing before it returns."""
        self.assertTrue(self.switch.off_now())
        self.assertEqual([entry[0] for entry in self.session.log if entry[0] != "event"][:2], ["acquire", "breath"])
        self.assertIn("GestureSwitch/ArmsTaken", self.event_names())

    def test_off_now_reports_failure_when_the_arms_cannot_be_taken(self):
        self.session.resources.busy = True
        self.assertFalse(self.switch.off_now())
        self.assertNotIn("GestureSwitch/ArmsTaken", self.event_names())


class CheckTests(SwitchTestCase):
    def deliver_instructions(self):
        """Makes the fake speech call ping() for the ping instruction, as NAOqi does."""
        def deliver(text):
            if text == "^pCall(GestureSwitch.ping())":
                self.switch.ping()
        self.session.speech.deliver = deliver

    def test_the_check_passes_when_naoqi_calls_the_switch(self):
        """check() says only the ping instruction, in disabled mode, and writes True."""
        self.deliver_instructions()
        self.assertTrue(check(self.switch, self.session.speech, self.session.memory, 0.2))
        self.assertEqual(self.session.speech.calls, [("^pCall(GestureSwitch.ping())", {"bodyLanguageMode": "disabled"})])
        self.assertIs(self.session.memory.data["GestureSwitch/Reachable"], True)

    def test_the_check_fails_when_the_instruction_is_lost(self):
        """check() writes False if NAOqi does not call ping() within the wait."""
        self.assertFalse(check(self.switch, self.session.speech, self.session.memory, 0.2))
        self.assertIs(self.session.memory.data["GestureSwitch/Reachable"], False)

    def test_a_ping_from_an_earlier_check_does_not_pass_a_later_one(self):
        """A ping from an earlier check does not pass the next check."""
        self.switch.ping()
        self.assertFalse(check(self.switch, self.session.speech, self.session.memory, 0.1))

    def test_the_check_repeats_until_it_passes_then_stops(self):
        """check_until_reachable stops after the first check that passes."""
        attempts = []

        def deliver(text):
            attempts.append(text)
            if len(attempts) == 3:
                self.switch.ping()
        self.session.speech.deliver = deliver
        stop = threading.Event()
        thread = threading.Thread(target=check_until_reachable, args=(self.switch, self.session.speech, self.session.memory, 0.05, 0.05, stop))
        thread.start()
        thread.join(timeout=2.0)
        stop.set()
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(attempts), 3)
        self.assertIs(self.session.memory.data["GestureSwitch/Reachable"], True)


if __name__ == "__main__":
    unittest.main()
