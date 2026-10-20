"""Tests for the gesture switch."""
import math
import threading
import time
import unittest

from gesture_switch import GestureSwitch, check, check_until_reachable

ARM_JOINTS = ["LShoulderPitch", "LShoulderRoll", "LElbowYaw", "LElbowRoll", "LWristYaw", "LHand",
              "RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "RWristYaw", "RHand"]
ANIMATION = "angleInterpolationBezier"
CONFIG = {
    "wait_limit_s": 1.0,
    "acquire_timeout_s": 0.2,
    "poll_interval_s": 0.005,
    "gesture_speed_mm_s": 296.0,
    "retract_min_s": 0.6,
    "retract_max_s": 2.0,
    "check_wait_s": 0.2,
    "check_interval_s": 0.05,
    "rest_pose": dict((name, 0.0) for name in ARM_JOINTS),
}
# Shoulder-to-hand offset in mm with all arm joints at zero (elbow + wrist + hand).
REACH_X, REACH_Z = 181.2 + 150.0 + 69.5, 0.13 + 22.84 - 30.3


class FakeMotion(object):
    """Fake ALMotion with a motion task list the test controls, an on_read hook that runs inside each read and a kill_fails flag that makes killTask return False; logs interpolations, breathing changes and killed tasks."""

    def __init__(self, log):
        self.log = log
        self.angles = dict((name, 0.0) for name in ARM_JOINTS)
        self.tasks = []
        self.killed = []
        self.next_id = 100
        self.failed_reads = 0
        self.interpolation_s = 0.0
        self.refuse_move = False
        self.on_read = None
        self.kill_fails = False

    def start_task(self, name=ANIMATION):
        self.next_id += 1
        self.tasks.append([name, self.next_id])
        return self.next_id

    def end_task(self, task_id):
        self.tasks = [t for t in self.tasks if t[1] != task_id]

    def getTaskList(self):
        if self.failed_reads > 0:
            self.failed_reads -= 1
            raise RuntimeError("no route to the robot")
        if self.on_read is not None:
            self.on_read()
        return [list(t) for t in self.tasks]

    def killTask(self, task_id):
        if self.kill_fails:
            return False
        self.killed.append(task_id)
        self.end_task(task_id)
        self.log.append(("kill", task_id))
        return True

    def getAngles(self, names, use_sensors):
        return [self.angles[name] for name in names]

    def angleInterpolation(self, names, targets, times, absolute):
        """Runs as an angleInterpolation task for interpolation_s, or until killTask ends it."""
        self.log.append(("interpolate", list(names), list(targets), list(times), absolute))
        if self.refuse_move:
            raise RuntimeError("motion refused")
        task = self.start_task("angleInterpolation")
        end = time.time() + self.interpolation_s
        while time.time() < end and task not in self.killed:
            time.sleep(0.002)
        self.end_task(task)

    def setBreathEnabled(self, chain, enabled):
        self.log.append(("breath", chain, enabled))


class FakeResources(object):
    """Fake ALResourceManager; acquire fails while busy is True, and with a gate it waits up to timeout for the gate to open."""

    def __init__(self, log):
        self.log = log
        self.busy = False
        self.gate = None
        self.acquired = []

    def acquireResourcesTree(self, resources, owner, callback, timeout):
        if self.busy:
            raise RuntimeError("resource busy")
        if self.gate is not None and not self.gate.wait(timeout):
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
        self.declared = []

    def declareEvent(self, name):
        self.declared.append(name)

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
        self.motion = FakeMotion(self.log)
        self.resources = FakeResources(self.log)
        self.memory = FakeMemory(self.log)
        self.speech = FakeSpeech()

    def service(self, name):
        return {"ALMotion": self.motion, "ALResourceManager": self.resources, "ALMemory": self.memory, "ALAnimatedSpeech": self.speech}[name]


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
        self.switch = GestureSwitch(self.session, CONFIG)

    def tearDown(self):
        self.switch.on()

    def first_acquire_after(self, t0, limit=2.0):
        self.assertTrue(wait_until(lambda: self.session.resources.acquired, limit), "the switch never took the arms")
        return self.session.resources.acquired[0] - t0

    def event_names(self):
        return [name for name, _ in self.session.memory.events]

    def arm_breathing(self):
        """The last arm breathing setting the switch made, or None before any."""
        settings = [entry[2] for entry in self.session.log if entry[0] == "breath" and entry[1] == "Arms"]
        return settings[-1] if settings else None

    def off_timed_out_after(self):
        """The seconds OffTimedOut reports, once it comes."""
        self.assertTrue(wait_until(lambda: "GestureSwitch/OffTimedOut" in self.event_names()))
        return [value for name, value in self.session.memory.events if name == "GestureSwitch/OffTimedOut"][0]


class OffTimingTests(SwitchTestCase):
    def test_off_returns_while_an_animation_is_still_running(self):
        """off() returns before the running animation ends."""
        self.session.motion.start_task()
        t = time.time()
        self.switch.off()
        self.assertLess(time.time() - t, 0.05)
        self.assertEqual(self.session.resources.acquired, [])

    def test_the_arms_are_taken_once_the_animations_running_at_off_have_ended(self):
        """off() takes the arms when the last animation task running at off() ends."""
        t0 = time.time()
        task = self.session.motion.start_task()
        self.switch.off()
        time.sleep(0.3)
        self.session.motion.end_task(task)
        self.assertAlmostEqual(self.first_acquire_after(t0), 0.3, delta=0.04)

    def test_the_arms_are_taken_at_once_when_no_animation_runs(self):
        t0 = time.time()
        self.switch.off()
        self.assertLess(self.first_acquire_after(t0), 0.04)

    def test_other_motion_tasks_are_not_waited_for(self):
        """off() takes the arms at once while only tracking and interpolation tasks run."""
        self.session.motion.start_task("LookAtWithSpeed")
        self.session.motion.start_task("angleInterpolation")
        t0 = time.time()
        self.switch.off()
        self.assertLess(self.first_acquire_after(t0), 0.04)

    def test_an_animation_starting_after_off_does_not_extend_the_wait(self):
        """off() waits only for the animation tasks running when it starts."""
        t0 = time.time()
        first = self.session.motion.start_task()
        self.switch.off()
        time.sleep(0.1)
        self.session.motion.start_task()
        time.sleep(0.2)
        self.session.motion.end_task(first)
        self.assertAlmostEqual(self.first_acquire_after(t0), 0.3, delta=0.04)

    def test_the_wait_gives_up_after_the_wait_limit(self):
        """If the animations running at off() never end, off() raises OffTimedOut at wait_limit_s, and starts neither breathing nor taking the arms."""
        self.session.motion.start_task()
        self.switch.off()
        self.assertAlmostEqual(self.off_timed_out_after(), CONFIG["wait_limit_s"], delta=0.05)
        self.assertEqual(self.session.resources.acquired, [])
        self.assertNotIn("interpolate", [entry[0] for entry in self.session.log])
        self.assertNotIn(("breath", "Arms", True), self.session.log)

    def test_breathing_starts_once_the_animations_running_at_off_have_ended(self):
        """off() starts arm breathing when the last animation task running at off() ends, and not before."""
        task = self.session.motion.start_task()
        self.switch.off()
        time.sleep(0.3)
        self.assertNotIn(("breath", "Arms", True), self.session.log)
        self.session.motion.end_task(task)
        ended = time.time()
        self.assertTrue(wait_until(lambda: ("breath", "Arms", True) in self.session.log))
        self.assertLess(time.time() - ended, 0.04)

    def test_breathing_starts_at_the_finish_while_the_arms_cannot_be_taken(self):
        """When the animations running at off() have ended and the arms stay held elsewhere, off() starts arm breathing at once and only once, then raises OffTimedOut at wait_limit_s."""
        self.session.resources.busy = True
        task = self.session.motion.start_task()
        self.switch.off()
        time.sleep(0.1)
        self.session.motion.end_task(task)
        ended = time.time()
        self.assertTrue(wait_until(lambda: ("breath", "Arms", True) in self.session.log))
        self.assertLess(time.time() - ended, 0.04)
        self.assertAlmostEqual(self.off_timed_out_after(), CONFIG["wait_limit_s"], delta=0.05)
        self.assertEqual(self.session.log.count(("breath", "Arms", True)), 1)
        self.assertTrue(self.arm_breathing())
        self.assertEqual(self.session.resources.acquired, [])

    def test_the_take_is_tried_again_until_the_arms_come_free(self):
        """When the arms stay held elsewhere after the animations running at off() end, off() keeps trying to take them, takes them as soon as they come free within wait_limit_s, and retracts them."""
        self.session.resources.busy = True
        task = self.session.motion.start_task()
        self.switch.off()
        time.sleep(0.1)
        self.session.motion.end_task(task)
        time.sleep(0.3)
        self.assertEqual(self.session.resources.acquired, [])
        freed = time.time()
        self.session.resources.busy = False
        self.assertTrue(wait_until(lambda: "GestureSwitch/Retracted" in self.event_names()))
        self.assertLess(self.session.resources.acquired[0] - freed, 0.04)
        self.assertNotIn("GestureSwitch/OffTimedOut", self.event_names())


class CancelTests(SwitchTestCase):
    def test_on_cancels_an_off_still_waiting(self):
        """on() cancels a waiting off(), which then raises OffCancelled and does not take the arms."""
        task = self.session.motion.start_task()
        self.switch.off()
        time.sleep(0.1)
        self.switch.on()
        self.session.motion.end_task(task)
        time.sleep(0.3)
        self.assertEqual(self.session.resources.acquired, [])
        self.assertIn("GestureSwitch/OffCancelled", self.event_names())

    def test_on_frees_the_arms(self):
        self.switch.off()
        wait_until(lambda: "GestureSwitch/Retracted" in self.event_names())
        self.switch.on()
        self.assertEqual(self.session.log[-2:], [("release", ["Left arm", "Right arm"], "GestureSwitch"), ("event", "GestureSwitch/On")])


class KillTests(SwitchTestCase):
    def off_and_take_the_arms(self):
        self.switch.off()
        self.assertTrue(wait_until(lambda: "GestureSwitch/ArmsTaken" in self.event_names()))

    def test_an_animation_starting_after_the_arms_are_taken_is_killed(self):
        """After off() takes the arms, the switch kills a new animation task and raises TaskKilled with its id."""
        self.off_and_take_the_arms()
        task = self.session.motion.start_task()
        self.assertTrue(wait_until(lambda: task in self.session.motion.killed, 0.5))
        self.assertIn(("GestureSwitch/TaskKilled", task), self.session.memory.events)

    def test_an_animation_starting_before_the_arms_are_taken_is_killed(self):
        """The switch kills an animation task that starts after off() while the running one finishes, before it takes the arms, and lets the running one finish."""
        running = self.session.motion.start_task()
        self.switch.off()
        time.sleep(0.05)
        later = self.session.motion.start_task()
        self.assertTrue(wait_until(lambda: later in self.session.motion.killed, 0.1))
        self.assertEqual(self.session.resources.acquired, [])
        self.assertNotIn(running, self.session.motion.killed)

    def test_an_animation_that_killtask_does_not_kill_raises_no_taskkilled(self):
        """When killTask returns False, the switch raises no TaskKilled for that task."""
        self.off_and_take_the_arms()
        self.session.motion.kill_fails = True
        self.session.motion.start_task()
        time.sleep(0.1)
        self.assertNotIn("GestureSwitch/TaskKilled", self.event_names())

    def test_other_motion_tasks_are_not_killed_while_off(self):
        """Tracking and interpolation tasks keep running while the switch is off."""
        self.off_and_take_the_arms()
        self.session.motion.start_task("LookAtWithSpeed")
        self.session.motion.start_task("angleInterpolation")
        time.sleep(0.2)
        self.assertEqual(self.session.motion.killed, [])

    def test_no_animation_is_killed_after_on(self):
        self.off_and_take_the_arms()
        self.switch.on()
        time.sleep(0.05)
        self.session.motion.start_task()
        time.sleep(0.2)
        self.assertEqual(self.session.motion.killed, [])

    def test_an_animation_starting_after_an_on_inside_a_kill_read_is_not_killed(self):
        """When on() and a new animation both come while the kill thread reads the task list, the switch kills nothing."""
        self.assertTrue(self.switch.off_now())
        started = []

        def on_then_start():
            self.session.motion.on_read = None
            self.switch.on()
            started.append(self.session.motion.start_task())
        self.session.motion.on_read = on_then_start
        self.assertTrue(wait_until(lambda: started))
        time.sleep(0.05)
        self.assertEqual(self.session.motion.killed, [])
        self.assertNotIn("GestureSwitch/TaskKilled", self.event_names())


class FailureTests(SwitchTestCase):
    def test_a_task_list_that_cannot_be_read_at_off_is_read_on_the_first_kill_poll(self):
        """When off() cannot read the task list, the animations running at the first reading after off() finish, and the switch kills later ones."""
        running = self.session.motion.start_task()
        self.session.motion.failed_reads = 1
        self.switch.off()
        time.sleep(0.05)
        later = self.session.motion.start_task()
        self.assertTrue(wait_until(lambda: later in self.session.motion.killed, 0.5))
        self.assertNotIn(running, self.session.motion.killed)
        self.assertEqual(self.session.memory.events[0], ("GestureSwitch/OffRequested", None))
        self.session.motion.end_task(running)
        self.assertTrue(wait_until(lambda: "GestureSwitch/ArmsTaken" in self.event_names()))

    def test_the_wait_goes_on_after_a_failed_task_list_read(self):
        """Breathing and the take wait through failed task list reads until a read shows the animations running at off() have ended."""
        task = self.session.motion.start_task()
        self.switch.off()
        self.session.motion.failed_reads = 3
        time.sleep(0.1)
        self.assertNotIn(("breath", "Arms", True), self.session.log)
        self.assertEqual(self.session.resources.acquired, [])
        self.session.motion.end_task(task)
        self.assertTrue(wait_until(lambda: "GestureSwitch/ArmsTaken" in self.event_names()))

    def test_an_off_that_on_cancelled_leaves_the_arms_a_later_off_took(self):
        """Two off() calls wait to take the arms around an on(); when both acquire, only the later one keeps them, and only on() releases."""
        self.session.resources.gate = threading.Event()
        self.switch.off()
        time.sleep(0.05)
        self.switch.on()
        self.switch.off()
        time.sleep(0.05)
        self.session.resources.gate.set()
        self.assertTrue(wait_until(lambda: "GestureSwitch/Retracted" in self.event_names()))
        time.sleep(0.1)
        self.assertEqual(len([entry for entry in self.session.log if entry[0] == "release"]), 1)


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

    def test_breathing_starts_then_the_arms_go_to_the_rest_pose(self):
        """off() starts arm breathing once, then takes the arms and moves every arm joint to its rest angle."""
        self.switch.off()
        self.assertTrue(wait_until(lambda: "GestureSwitch/Retracted" in self.event_names()))
        motor = [entry for entry in self.session.log if entry[0] != "event"]
        self.assertEqual([entry[0] for entry in motor[:3]], ["breath", "acquire", "interpolate"])
        self.assertEqual(motor[0], ("breath", "Arms", True))
        self.assertEqual(self.session.log.count(("breath", "Arms", True)), 1)
        self.assertTrue(self.arm_breathing())
        _, names, targets, _, absolute = motor[2]
        self.assertEqual(sorted(names), sorted(ARM_JOINTS))
        self.assertEqual(targets, [0.0] * len(ARM_JOINTS))
        self.assertTrue(absolute)

    def test_the_retraction_moves_the_hands_at_gesture_speed(self):
        """The retraction time is the hand distance divided by the gesture speed."""
        reach = math.hypot(REACH_X, REACH_Z)
        self.set_shoulder_pitch(2 * math.asin(296.0 / (2 * reach)))
        self.assertAlmostEqual(self.retraction_time(), 1.0, places=2)

    def test_on_during_the_retraction_stops_it_and_reports_no_retracted(self):
        """on() that arrives while the arms return kills the retraction task, the switch reports no Retracted, and breathing stays as off() started it."""
        self.session.motion.interpolation_s = 0.5
        self.switch.off()
        self.assertTrue(wait_until(lambda: any(entry[0] == "interpolate" for entry in self.session.log)))
        time.sleep(0.05)
        self.switch.on()
        self.assertTrue(wait_until(lambda: any(entry[0] == "kill" for entry in self.session.log), 0.3))
        time.sleep(0.1)
        self.assertEqual(self.session.log.count(("breath", "Arms", True)), 1)
        self.assertTrue(self.arm_breathing())
        self.assertNotIn("GestureSwitch/Retracted", self.event_names())

    def test_retracted_reports_the_seconds_the_move_took(self):
        self.session.motion.interpolation_s = 0.2
        self.switch.off()
        self.assertTrue(wait_until(lambda: "GestureSwitch/Retracted" in self.event_names()))
        took = [value for name, value in self.session.memory.events if name == "GestureSwitch/Retracted"][0]
        self.assertAlmostEqual(took, 0.2, delta=0.05)

    def test_a_refused_move_reports_null_with_breathing_on(self):
        self.session.motion.refuse_move = True
        self.switch.off()
        self.assertTrue(wait_until(lambda: "GestureSwitch/Retracted" in self.event_names()))
        self.assertIn(("GestureSwitch/Retracted", None), self.session.memory.events)
        self.assertTrue(self.arm_breathing())

    def test_a_retraction_missing_from_the_first_task_list_read_is_still_killed(self):
        """When the read at on() fails, the switch reads again and kills the retraction."""
        self.session.motion.interpolation_s = 0.5
        self.switch.off()
        self.assertTrue(wait_until(lambda: any(entry[0] == "interpolate" for entry in self.session.log)))
        time.sleep(0.05)
        self.session.motion.failed_reads = 2
        self.switch.on()
        self.assertTrue(wait_until(lambda: any(entry[0] == "kill" for entry in self.session.log), 0.3))

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
        """off() raises OffRequested with the ids of the animation tasks running at off(), then ArmsTaken, then Retracted."""
        task = self.session.motion.start_task()
        self.switch.off()
        time.sleep(0.05)
        self.session.motion.end_task(task)
        self.assertTrue(wait_until(lambda: "GestureSwitch/Retracted" in self.event_names()))
        self.assertEqual(self.event_names(), ["GestureSwitch/OffRequested", "GestureSwitch/ArmsTaken", "GestureSwitch/Retracted"])
        self.assertEqual(self.session.memory.events[0][1], [task])

    def test_every_event_is_declared_when_the_switch_starts(self):
        """The switch declares every event it raises when it starts."""
        declared = list(self.session.memory.declared)
        self.switch.off()
        self.assertTrue(wait_until(lambda: "GestureSwitch/Retracted" in self.event_names()))
        task = self.session.motion.start_task()
        self.assertTrue(wait_until(lambda: task in self.session.motion.killed, 0.5))
        self.switch.on()
        raised = set(self.event_names())
        self.assertEqual(raised - set(declared), set())
        self.assertTrue(set(["GestureSwitch/OffCancelled", "GestureSwitch/OffTimedOut"]) <= set(declared))


class OffNowTests(SwitchTestCase):
    def test_off_now_returns_with_breathing_on_and_the_arms_taken(self):
        """off_now() starts arm breathing, then takes the arms, before it returns."""
        self.assertTrue(self.switch.off_now())
        self.assertEqual([entry[0] for entry in self.session.log if entry[0] != "event"][:2], ["breath", "acquire"])
        self.assertTrue(self.arm_breathing())
        self.assertIn("GestureSwitch/ArmsTaken", self.event_names())

    def test_off_now_reports_failure_when_the_arms_cannot_be_taken(self):
        self.session.resources.busy = True
        self.assertFalse(self.switch.off_now())
        self.assertNotIn("GestureSwitch/ArmsTaken", self.event_names())

    def test_off_now_starts_breathing_even_when_the_arms_cannot_be_taken(self):
        self.session.resources.busy = True
        self.assertFalse(self.switch.off_now())
        self.assertTrue(self.arm_breathing())

    def test_off_now_stops_new_animations_even_when_the_arms_cannot_be_taken(self):
        self.session.resources.busy = True
        self.assertFalse(self.switch.off_now())
        later = self.session.motion.start_task()
        self.assertTrue(wait_until(lambda: later in self.session.motion.killed, 0.5))

    def test_off_now_kills_animations_that_start_afterwards_and_lets_running_ones_finish(self):
        running = self.session.motion.start_task()
        self.assertTrue(self.switch.off_now())
        later = self.session.motion.start_task()
        self.assertTrue(wait_until(lambda: later in self.session.motion.killed, 0.5))
        self.assertNotIn(running, self.session.motion.killed)


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
