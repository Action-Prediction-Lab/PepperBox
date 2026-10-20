# py3-naoqi-bridge/gesture_switch.py (Python 2)
"""NAOqi service that stops and starts Pepper's co-speech gestures during animated speech."""
from __future__ import print_function
import json
import math
import os
import sys
import threading
import time

from robot_address import callback_ip
from stop_signals import catch_stop_signals


SERVICE = "GestureSwitch"
ARMS = ["Left arm", "Right arm"]
ANIMATION_TASK = "angleInterpolationBezier"
RETRACTION_TASK = "angleInterpolation"
PING_INSTRUCTION = "^pCall(%s.ping())" % SERVICE
REACHABLE = SERVICE + "/Reachable"
EVENTS = ("OffRequested", "ArmsTaken", "Retracted", "On", "OffCancelled", "OffTimedOut", "TaskKilled")
CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config")
CONFIG_FILE = os.path.join(CONFIG_DIR, "gesture_switch.json")
# Arm link offsets in mm, from doc.aldebaran.com/2-5/family/pepper_technical/links_pep.html.
SHOULDER = {"L": (-57.0, 149.74, 86.82), "R": (-57.0, -149.74, 86.82)}
ELBOW = {"L": (181.2, 15.0, 0.13), "R": (181.2, -15.0, 0.13)}
WRIST = {"L": (150.0, 23.6, 22.84), "R": (150.0, -23.6, 22.84)}
HAND = (69.5, 0.0, -30.3)


def _rotation(axis, a):
    c, s = math.cos(a), math.sin(a)
    if axis == "x":
        return [[1, 0, 0], [0, c, -s], [0, s, c]]
    if axis == "y":
        return [[c, 0, s], [0, 1, 0], [-s, 0, c]]
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _apply(m, v):
    return [sum(m[i][k] * v[k] for k in range(3)) for i in range(3)]


def hand_position(side, angles):
    """Returns the hand position in mm in the torso frame for side "L" or "R"."""
    sp, sr, ey, er, wy = [angles[side + name] for name in ("ShoulderPitch", "ShoulderRoll", "ElbowYaw", "ElbowRoll", "WristYaw")]
    upper = _matmul(_rotation("y", sp), _rotation("z", sr))
    fore = _matmul(_matmul(upper, _rotation("x", ey)), _rotation("z", er))
    hand = _matmul(fore, _rotation("x", wy))
    parts = [SHOULDER[side], _apply(upper, ELBOW[side]), _apply(fore, WRIST[side]), _apply(hand, HAND)]
    return [sum(p[i] for p in parts) for i in range(3)]


def _distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


class GestureSwitch(object):
    """Stops and starts Pepper's gestures for the ^pCall instructions that call it."""

    def __init__(self, session, config):
        self._config = config
        self._rest = config["rest_pose"]
        self._joints = sorted(self._rest)
        self._rest_hands = dict((side, hand_position(side, self._rest)) for side in "LR")
        self._motion = session.service("ALMotion")
        self._resources = session.service("ALResourceManager")
        self._memory = session.service("ALMemory")
        self._lock = threading.Lock()
        self._generation = 0
        self._held_by = None
        self._taking = {}
        self._pinged = threading.Event()
        for name in EVENTS:
            self._memory.declareEvent(SERVICE + "/" + name)

    def _tasks(self, name):
        """Ids of the ALMotion tasks with this name that are running now."""
        return set(task_id for task, task_id in self._motion.getTaskList() if task == name)

    def _read_animations(self):
        """Ids of the animation tasks running now, or None when the switch cannot read ALMotion."""
        try:
            return self._tasks(ANIMATION_TASK)
        except Exception as e:
            sys.stderr.write("gesture_switch: cannot read the task list: %s\n" % e)
            return None

    def _current(self, generation):
        with self._lock:
            return generation == self._generation

    def _event(self, name, value):
        try:
            self._memory.raiseEvent(SERVICE + "/" + name, value)
        except Exception as e:
            sys.stderr.write("gesture_switch: cannot raise %s: %s\n" % (name, e))

    def _take_arms(self, generation, timeout):
        """Takes the arms for generation; returns True if generation is still current and now holds them, and gives back arms a stale generation took unless the current one holds or is taking them."""
        with self._lock:
            self._taking[generation] = self._taking.get(generation, 0) + 1
        try:
            self._resources.acquireResourcesTree(ARMS, SERVICE, "onConflict", timeout)
            taken = True
        except Exception:
            taken = False
        with self._lock:
            self._taking[generation] -= 1
            if not self._taking[generation]:
                del self._taking[generation]
            if not taken:
                return False
            if generation == self._generation:
                self._held_by = generation
                return True
            if self._held_by != self._generation and self._generation not in self._taking:
                self._release_arms()
        return False

    def _breathe(self):
        """Starts arm breathing, which animated speech switches off for the whole call."""
        try:
            self._motion.setBreathEnabled("Arms", True)
        except Exception as e:
            sys.stderr.write("gesture_switch: cannot start arm breathing: %s\n" % e)

    def _release_arms(self):
        try:
            self._resources.releaseResources(ARMS, SERVICE)
        except Exception as e:
            sys.stderr.write("gesture_switch: cannot free the arms: %s\n" % e)

    def off(self):
        """Stops new animations from now until on(), lets the animations running now finish, then starts arm breathing, takes the arms and retracts them; returns at once."""
        with self._lock:
            generation = self._generation
        snapshot = {"running": self._read_animations()}
        running = snapshot["running"]
        self._event("OffRequested", sorted(running) if running is not None else None)
        self._kill_new_animations(generation, snapshot)
        thread = threading.Thread(target=self._off, args=(generation, time.time(), snapshot))
        thread.daemon = True
        thread.start()

    def _off(self, generation, requested, snapshot):
        c = self._config
        held = breathing = False
        while time.time() < requested + c["wait_limit_s"] and self._current(generation):
            if snapshot["running"] is not None:
                tasks = self._read_animations()
                if tasks is not None and not snapshot["running"] & tasks:
                    if not breathing:
                        self._breathe()
                        breathing = True
                    held = self._take_arms(generation, c["acquire_timeout_s"])
                    if held:
                        break
            time.sleep(c["poll_interval_s"])
        waited = time.time() - requested
        if not self._current(generation):
            self._event("OffCancelled", waited)
            return
        if not held:
            self._event("OffTimedOut", waited)
            return
        self._event("ArmsTaken", waited)
        self._retract(generation)

    def _retract(self, generation):
        """Moves the arms to the rest pose at gesture speed, and kills the move when on() comes first."""
        c = self._config
        try:
            angles = dict(zip(self._joints, self._motion.getAngles(self._joints, False)))
            distance = max(_distance(hand_position(side, angles), self._rest_hands[side]) for side in "LR")
            seconds = min(c["retract_max_s"], max(c["retract_min_s"], distance / c["gesture_speed_mm_s"]))
        except Exception as e:
            sys.stderr.write("gesture_switch: cannot read the arm angles: %s\n" % e)
            seconds = c["retract_max_s"]
        try:
            before = self._tasks(RETRACTION_TASK)
        except Exception:
            before = set()
        done = threading.Event()
        moved = []

        def move():
            try:
                self._motion.angleInterpolation(self._joints, [self._rest[name] for name in self._joints], [seconds] * len(self._joints), True)
                moved.append(True)
            except Exception as e:
                sys.stderr.write("gesture_switch: retraction failed: %s\n" % e)
            finally:
                done.set()
        started = time.time()
        thread = threading.Thread(target=move)
        thread.daemon = True
        thread.start()
        while not done.wait(c["poll_interval_s"]):
            if not self._current(generation):
                self._kill_retraction(before, done)
                return
        took = time.time() - started
        if not self._current(generation):
            return
        self._event("Retracted", round(took, 3) if moved else None)

    def _kill_retraction(self, before, done):
        """Kills every retraction task missing from before until the move returns, for at most retract_max_s."""
        c = self._config
        end = time.time() + c["retract_max_s"]
        while not done.is_set() and time.time() < end:
            try:
                for task_id in self._tasks(RETRACTION_TASK) - before:
                    self._motion.killTask(task_id)
            except Exception as e:
                sys.stderr.write("gesture_switch: cannot stop the retraction: %s\n" % e)
            done.wait(c["poll_interval_s"])

    def _kill_new_animations(self, generation, snapshot):
        """Kills every animation task missing from snapshot["running"] until on(); when off() or off_now() could not read the task list, the first reading here fills the snapshot."""
        def kill():
            while self._current(generation):
                try:
                    tasks = self._tasks(ANIMATION_TASK)
                    if snapshot["running"] is None:
                        snapshot["running"] = tasks
                    for task_id in tasks - snapshot["running"]:
                        with self._lock:
                            if generation != self._generation:
                                break
                            killed = self._motion.killTask(task_id)
                        if killed:
                            self._event("TaskKilled", task_id)
                except Exception as e:
                    sys.stderr.write("gesture_switch: cannot stop an animation: %s\n" % e)
                time.sleep(self._config["poll_interval_s"])
        thread = threading.Thread(target=kill)
        thread.daemon = True
        thread.start()

    def off_now(self):
        """Stops new animations until on(), starts arm breathing and takes the arms at once; returns True if it took the arms."""
        with self._lock:
            generation = self._generation
        self._kill_new_animations(generation, {"running": self._read_animations()})
        self._breathe()
        if not self._take_arms(generation, self._config["acquire_timeout_s"]):
            return False
        self._event("ArmsTaken", 0.0)
        return True

    def on(self):
        """Frees the arms, cancels a waiting off(), stops a retraction and lets new animations run."""
        with self._lock:
            self._generation += 1
            self._held_by = None
            self._release_arms()
        self._event("On", True)

    def ping(self):
        """Records that NAOqi called the switch."""
        self._pinged.set()
        return True

    def onConflict(self, resource, owner):
        """Keeps the arms when another module requests them."""


def check(switch, speech, memory, wait_s):
    """Says a silent ping instruction and writes the result to GestureSwitch/Reachable."""
    switch._pinged.clear()
    try:
        speech.say(PING_INSTRUCTION, {"bodyLanguageMode": "disabled"})
        reached = switch._pinged.wait(wait_s)
        if not reached:
            sys.stderr.write("gesture_switch: NAOqi did not call the switch within %.1f s, so ^pCall instructions in speech are being lost\n" % wait_s)
    except Exception as e:
        sys.stderr.write("gesture_switch: reachability check failed: %s\n" % e)
        reached = False
    memory.insertData(REACHABLE, reached)
    return reached


def check_until_reachable(switch, speech, memory, wait_s, interval_s, stop):
    """Repeats the check every interval_s until it passes or stop is set."""
    while not stop.is_set():
        if check(switch, speech, memory, wait_s):
            return True
        stop.wait(interval_s)
    return False


def read_json(path):
    with open(path) as f:
        return json.load(f)


def main():
    try:
        import qi
    except ImportError:
        sys.stderr.write("gesture_switch: qi not importable; exiting.\n")
        return 2

    try:
        config = read_json(CONFIG_FILE)
    except (IOError, ValueError) as e:
        sys.stderr.write("gesture_switch: cannot read the config: %s\n" % e)
        return 5

    naoqi_ip = os.environ.get("NAOQI_IP", "127.0.0.1")
    naoqi_port = int(os.environ.get("NAOQI_PORT", "9559"))
    listen_ip = callback_ip(naoqi_ip, naoqi_port)
    app = qi.Application(["gesture_switch", "--qi-url=tcp://%s:%d" % (naoqi_ip, naoqi_port), "--qi-listen-url=tcp://%s:0" % listen_ip])
    try:
        app.start()
    except RuntimeError as e:
        sys.stderr.write("gesture_switch: NAOqi unreachable at %s:%d: %s\n" % (naoqi_ip, naoqi_port, e))
        return 3

    session = app.session
    dropped = threading.Event()
    session.disconnected.connect(lambda reason: dropped.set())
    memory = session.service("ALMemory")
    memory.insertData(REACHABLE, False)
    switch = GestureSwitch(session, config)
    try:
        session.registerService(SERVICE, switch)
    except RuntimeError as e:
        sys.stderr.write("gesture_switch: cannot register %s: %s\n" % (SERVICE, e))
        return 6
    switch.on()
    stop = threading.Event()
    checker = threading.Thread(target=check_until_reachable, args=(switch, session.service("ALAnimatedSpeech"), memory, config["check_wait_s"], config["check_interval_s"], stop))
    checker.daemon = True
    checker.start()
    sys.stderr.write("gesture_switch: serving %s on %s for %s:%d\n" % (SERVICE, listen_ip, naoqi_ip, naoqi_port))
    catch_stop_signals()

    try:
        while not dropped.wait(1.0):
            pass
        sys.stderr.write("gesture_switch: robot session dropped; exiting\n")
        return 4
    except KeyboardInterrupt:
        switch.on()
        try:
            memory.insertData(REACHABLE, False)
        except Exception as e:
            sys.stderr.write("gesture_switch: cannot clear %s: %s\n" % (REACHABLE, e))
        return 0
    finally:
        stop.set()


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
