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


SERVICE = "GestureSwitch"
ARMS = ["Left arm", "Right arm"]
ANIMATIONS = "animations/"
PING_INSTRUCTION = "^pCall(%s.ping())" % SERVICE
REACHABLE = SERVICE + "/Reachable"
CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config")
CONFIG_FILE = os.path.join(CONFIG_DIR, "gesture_switch.json")
DURATIONS_FILE = os.path.join(CONFIG_DIR, "animation_durations.json")
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
    """Stops and starts arm gestures for the ^pCall instructions that call it."""

    def __init__(self, session, config, durations):
        self._config = config
        self._durations = durations
        self._rest = config["rest_pose"]
        self._joints = sorted(self._rest)
        self._rest_hands = dict((side, hand_position(side, self._rest)) for side in "LR")
        self._motion = session.service("ALMotion")
        self._resources = session.service("ALResourceManager")
        self._memory = session.service("ALMemory")
        self._lock = threading.Lock()
        self._running = {}
        self._generation = 0
        self._held = False
        self._pinged = threading.Event()
        behaviors = session.service("ALBehaviorManager")
        behaviors.behaviorStarted.connect(self._started)
        behaviors.behaviorStopped.connect(self._stopped)

    def _started(self, name):
        if name.startswith(ANIMATIONS):
            with self._lock:
                self._running[name] = time.time()

    def _stopped(self, name):
        with self._lock:
            self._running.pop(name, None)

    def _moving(self):
        with self._lock:
            return dict(self._running)

    def _current(self, generation):
        with self._lock:
            return generation == self._generation

    def _event(self, name, value):
        try:
            self._memory.raiseEvent(SERVICE + "/" + name, value)
        except Exception as e:
            sys.stderr.write("gesture_switch: cannot raise %s: %s\n" % (name, e))

    def _take_arms(self, timeout):
        try:
            self._resources.acquireResourcesTree(ARMS, SERVICE, "onConflict", timeout)
        except Exception:
            return False
        self._held = True
        return True

    def _free(self):
        try:
            self._resources.releaseResources(ARMS, SERVICE)
        except Exception as e:
            sys.stderr.write("gesture_switch: cannot free the arms: %s\n" % e)
        self._held = False

    def off(self):
        """Lets the current gesture finish, then takes the arms and retracts them; returns at once."""
        with self._lock:
            generation = self._generation
        self._event("OffRequested", sorted(self._moving()))
        thread = threading.Thread(target=self._off, args=(generation, time.time()))
        thread.daemon = True
        thread.start()

    def _off(self, generation, requested):
        c = self._config
        while time.time() < requested + c["wait_limit_s"] and self._current(generation):
            moving = self._moving()
            if not moving:
                if self._take_arms(0):
                    break
                time.sleep(c["poll_interval_s"])
                continue
            end = max(t + self._durations.get(name, c["default_duration_s"]) for name, t in moving.items())
            while time.time() < end - c["lead_s"] and self._moving() == moving and self._current(generation):
                time.sleep(c["poll_interval_s"])
            if not self._current(generation):
                break
            if self._moving() != moving and time.time() < end - c["lead_s"]:
                continue
            if self._take_arms(c["acquire_timeout_s"]):
                break
        waited = time.time() - requested
        if not self._current(generation):
            if self._held:
                self._free()
            self._event("OffCancelled", waited)
            return
        if not self._held:
            self._event("OffTimedOut", waited)
            return
        self._event("ArmsTaken", waited)
        self._retract()

    def _retract(self):
        """Moves the arms to the rest pose at gesture speed, then starts arm breathing."""
        c = self._config
        angles = dict(zip(self._joints, self._motion.getAngles(self._joints, False)))
        distance = max(_distance(hand_position(side, angles), self._rest_hands[side]) for side in "LR")
        seconds = min(c["retract_max_s"], max(c["retract_min_s"], distance / c["gesture_speed_mm_s"]))
        try:
            self._motion.angleInterpolation(self._joints, [self._rest[name] for name in self._joints], [seconds] * len(self._joints), True)
        except Exception as e:
            sys.stderr.write("gesture_switch: retraction failed: %s\n" % e)
        self._motion.setBreathEnabled("Arms", True)
        self._event("Retracted", seconds)

    def off_now(self):
        """Takes the arms immediately and starts arm breathing; returns True if it took the arms."""
        if not self._take_arms(self._config["acquire_timeout_s"]):
            return False
        self._motion.setBreathEnabled("Arms", True)
        self._event("ArmsTaken", 0.0)
        return True

    def on(self):
        """Frees the arms and cancels a waiting off()."""
        with self._lock:
            self._generation += 1
        self._free()
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
        durations = read_json(DURATIONS_FILE)["durations"]
    except (IOError, ValueError, KeyError) as e:
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
    switch = GestureSwitch(session, config, durations)
    try:
        session.registerService(SERVICE, switch)
    except RuntimeError as e:
        sys.stderr.write("gesture_switch: cannot register %s: %s\n" % (SERVICE, e))
        return 6
    switch.on()
    memory = session.service("ALMemory")
    memory.insertData(REACHABLE, False)
    stop = threading.Event()
    checker = threading.Thread(target=check_until_reachable, args=(switch, session.service("ALAnimatedSpeech"), memory, config["check_wait_s"], config["check_interval_s"], stop))
    checker.daemon = True
    checker.start()
    sys.stderr.write("gesture_switch: serving %s on %s for %s:%d\n" % (SERVICE, listen_ip, naoqi_ip, naoqi_port))

    try:
        while not dropped.wait(1.0):
            pass
        sys.stderr.write("gesture_switch: robot session dropped; exiting\n")
        return 4
    except KeyboardInterrupt:
        switch.on()
        return 0
    finally:
        stop.set()


if __name__ == "__main__":
    sys.exit(main())
