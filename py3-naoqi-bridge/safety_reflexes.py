# py3-naoqi-bridge/safety_reflexes.py (Python 2)
"""Applies NAOqi safety reflex settings from config/safety_reflexes.json, verifies them, exits when the robot session drops so the restart loop applies them again, and switches back on every protection it switched off when a setting fails or on SIGTERM or SIGINT."""
from __future__ import print_function
import json
import os
import sys
import threading
import time

from stop_signals import catch_stop_signals


CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "safety_reflexes.json")
REFLEXES = {"ExternalCollisionProtection": ("setExternalCollisionProtectionEnabled", "getExternalCollisionProtectionEnabled")}
TIMING = ("poll_interval_s", "wait_limit_s")


def read_reflexes(path):
    """Returns the read-back timing and the reflex settings in path; raises ValueError for a missing timing value, an unknown reflex or a value other than true or false."""
    with open(path) as f:
        reflexes = json.load(f)
    timing = {}
    for key in TIMING:
        if key not in reflexes:
            raise ValueError("missing %s" % key)
        timing[key] = reflexes.pop(key)
    for section, chains in reflexes.items():
        if section not in REFLEXES:
            raise ValueError("unknown safety reflex %r; known: %s" % (section, sorted(REFLEXES)))
        for chain, enabled in chains.items():
            if not isinstance(enabled, bool):
                raise ValueError("%s %s must be true or false, got %r" % (section, chain, enabled))
    return timing, reflexes


def back_on(reflexes):
    """The settings that switch back on each chain that reflexes switches off."""
    settings = {}
    for section, chains in reflexes.items():
        off = dict((chain, True) for chain, enabled in chains.items() if not enabled)
        if off:
            settings[section] = off
    return settings


def switch_back_on(motion, reflexes, timing):
    """Switches back on every protection that reflexes switches off, and logs the outcome."""
    settings = back_on(reflexes)
    try:
        apply_reflexes(motion, settings, **timing)
        sys.stderr.write("safety_reflexes: switched back on %s\n" % json.dumps(settings, sort_keys=True))
    except Exception as e:
        sys.stderr.write("safety_reflexes: cannot switch the protections back on: %s\n" % e)


def apply_reflexes(motion, reflexes, poll_interval_s, wait_limit_s):
    """Sets each reflex once, then reads it back every poll_interval_s until two reads in a row return the set value; raises RuntimeError if they do not within wait_limit_s of setting that chain."""
    for section, chains in sorted(reflexes.items()):
        setter, getter = (getattr(motion, name) for name in REFLEXES[section])
        for chain, enabled in sorted(chains.items()):
            setter(chain, enabled)
            agreed, deadline = 0, time.time() + wait_limit_s
            while agreed < 2:
                if time.time() > deadline:
                    raise RuntimeError("%s %s did not settle at %s" % (section, chain, enabled))
                time.sleep(poll_interval_s)
                agreed = agreed + 1 if getter(chain) == enabled else 0


def main():
    try:
        import qi
    except ImportError:
        sys.stderr.write("safety_reflexes: qi not importable; exiting.\n")
        return 2

    try:
        timing, reflexes = read_reflexes(CONFIG_FILE)
    except (IOError, ValueError) as e:
        sys.stderr.write("safety_reflexes: cannot read %s: %s\n" % (CONFIG_FILE, e))
        return 5

    naoqi_ip = os.environ.get("NAOQI_IP", "127.0.0.1")
    naoqi_port = int(os.environ.get("NAOQI_PORT", "9559"))
    app = qi.Application(["safety_reflexes", "--qi-url=tcp://%s:%d" % (naoqi_ip, naoqi_port)])
    try:
        app.start()
    except RuntimeError as e:
        sys.stderr.write("safety_reflexes: NAOqi unreachable at %s:%d: %s\n" % (naoqi_ip, naoqi_port, e))
        return 3

    session = app.session
    dropped = threading.Event()
    session.disconnected.connect(lambda reason: dropped.set())
    motion = session.service("ALMotion")
    catch_stop_signals()
    try:
        try:
            apply_reflexes(motion, reflexes, **timing)
            sys.stderr.write("safety_reflexes: applied %s\n" % json.dumps(reflexes, sort_keys=True))
        except RuntimeError as e:
            sys.stderr.write("safety_reflexes: %s\n" % e)
            switch_back_on(motion, reflexes, timing)
        while not dropped.wait(1.0):
            pass
        sys.stderr.write("safety_reflexes: robot session dropped; exiting\n")
        return 4
    except KeyboardInterrupt:
        switch_back_on(motion, reflexes, timing)
        return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
