# py3-naoqi-bridge/event_publisher.py (Python 2)
"""NAOqi behaviour signals, ALMemory events and polled ALMotion task lists and joint angles -> ZMQ PUB :5565, with a heartbeat each time the robot answers a ping."""
from __future__ import print_function
import fnmatch
import json
import os
import sys
import threading
import time
import Queue  # Py2
import zmq


EVENT_PUB_PORT = 5565
HEARTBEAT_S = 1.0
BEHAVIOR_SIGNALS = ("behaviorStarted", "behaviorStopped")
EVENTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "events.txt")
MOTION_POLL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "motion_poll.json")


def read_patterns(path):
    """Event name patterns from the config file, one per line; blank lines and lines starting with # are skipped."""
    with open(path) as f:
        lines = [line.strip() for line in f]
    return [line for line in lines if line and not line.startswith("#")]


def read_motion_poll(path):
    """The ALMotion polling settings from the config file; raises ValueError when getAngles comes without ndigits."""
    with open(path) as f:
        config = json.load(f)
    if "getAngles" in config and "ndigits" not in config:
        raise ValueError("%s: getAngles needs ndigits" % path)
    return config


def matches(name, patterns):
    """True when the event name matches any of the fnmatch patterns, case-sensitively."""
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def event_message(topic, value, t):
    """Topic and payload for one NAOqi signal or event; a value JSON cannot encode is sent as its repr."""
    try:
        json.dumps(value)
    except (TypeError, ValueError, UnicodeDecodeError):
        value = repr(value)
    return (topic, {"t": t, "value": value})


def connect(session, publisher, patterns):
    """Forward the behaviour signals and every ALMemory event matching patterns, including events declared later; returns the subscribers to keep alive."""
    def forward(topic, value):
        publisher.enqueue(event_message(topic, value, time.time()))

    behavior_manager = session.service("ALBehaviorManager")
    for name in BEHAVIOR_SIGNALS:
        topic = "ALBehaviorManager." + name
        getattr(behavior_manager, name).connect(lambda value, topic=topic: forward(topic, value))

    memory = session.service("ALMemory")
    lock = threading.Lock()
    subscribers = {}

    def subscribe(event):
        with lock:
            if event in subscribers or not matches(event, patterns):
                return
            subscriber = memory.subscriber(event)
            subscriber.signal.connect(lambda value, topic=event: forward(topic, value))
            subscribers[event] = subscriber

    def on_key_added(key):
        """Handle ALMemory/KeyAdded, which ALMemory raises with the name of every new key, event or data; subscribe only if it is an event."""
        if key in memory.getEventList():
            subscribe(key)

    def on_key_removed(key):
        """Handle ALMemory/KeyRemoved, which ALMemory raises with the name of every deleted key; forget its subscription."""
        with lock:
            subscribers.pop(key, None)

    watchers = [memory.subscriber("ALMemory/KeyAdded"), memory.subscriber("ALMemory/KeyRemoved")]
    watchers[0].signal.connect(on_key_added)
    watchers[1].signal.connect(on_key_removed)
    for event in memory.getEventList():
        subscribe(event)
    return {"watchers": watchers, "events": subscribers}


class PublisherThread(threading.Thread):
    """Owns the PUB socket and sends queued messages as topic and JSON frames."""

    def __init__(self, port=EVENT_PUB_PORT):
        threading.Thread.__init__(self)
        self.daemon = True
        self.queue = Queue.Queue(maxsize=256)
        self._stop = threading.Event()
        self._sock = zmq.Context.instance().socket(zmq.PUB)
        self._sock.bind("tcp://*:%d" % port)

    def enqueue(self, message):
        try:
            self.queue.put_nowait(message)
        except Queue.Full:
            # Drop rather than block the NAOqi dispatcher.
            sys.stderr.write("event_publisher: queue full; dropped one message\n")

    def stop(self):
        self._stop.set()

    def _send(self, topic, payload):
        try:
            self._sock.send_multipart([topic.encode("utf-8"), json.dumps(payload).encode("utf-8")])
        except zmq.ZMQError as e:
            sys.stderr.write("event_publisher: zmq send error: %s\n" % e)

    def run(self):
        while not self._stop.is_set():
            try:
                topic, payload = self.queue.get(timeout=0.05)
            except Queue.Empty:
                continue
            self._send(topic, payload)
        self._sock.close()


class HeartbeatThread(threading.Thread):
    """Pings the robot every heartbeat_s and enqueues a heartbeat for each answer, so heartbeats stop when the robot stops answering."""

    def __init__(self, memory, publisher, started, heartbeat_s=HEARTBEAT_S):
        threading.Thread.__init__(self)
        self.daemon = True
        self._memory = memory
        self._publisher = publisher
        self._started = started
        self._heartbeat_s = heartbeat_s
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            try:
                self._memory.ping()
                self._publisher.enqueue(("heartbeat", {"t": time.time(), "started": self._started}))
            except Exception as e:
                sys.stderr.write("event_publisher: robot ping failed: %s\n" % e)
            self._stop.wait(self._heartbeat_s)


class MotionPollThread(threading.Thread):
    """Polls ALMotion every poll_interval_s and enqueues its task list and, when the config has getAngles, its joint angles rounded to ndigits, each when it changes and again every heartbeat_s."""

    def __init__(self, motion, publisher, config, heartbeat_s=HEARTBEAT_S):
        threading.Thread.__init__(self)
        self.daemon = True
        self._motion = motion
        self._publisher = publisher
        self._poll_interval_s = config["poll_interval_s"]
        self._heartbeat_s = heartbeat_s
        self._angles = config.get("getAngles")
        self._ndigits = config["ndigits"] if self._angles else None
        self._names = motion.getBodyNames(self._angles["names"]) if self._angles else None
        self._sent = {}
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def _publish(self, topic, value):
        """Enqueue value on topic when it differs from the last value sent there or heartbeat_s has passed since."""
        now = time.time()
        last = self._sent.get(topic)
        if last is None or last[0] != value or now - last[1] >= self._heartbeat_s:
            self._publisher.enqueue(event_message(topic, value, now))
            self._sent[topic] = (value, now)

    def _poll(self):
        self._publish("ALMotion.getTaskList", self._motion.getTaskList())
        if self._angles:
            angles = [round(a, self._ndigits) for a in self._motion.getAngles(self._names, self._angles["useSensors"])]
            self._publish("ALMotion.getAngles", {"names": self._names, "useSensors": self._angles["useSensors"], "angles": angles})

    def run(self):
        due = time.time()
        while not self._stop.is_set():
            try:
                self._poll()
            except Exception as e:
                sys.stderr.write("event_publisher: ALMotion poll failed: %s\n" % e)
            due = max(due + self._poll_interval_s, time.time())
            self._stop.wait(due - time.time())


def start(session, started, patterns, motion_poll=None, port=EVENT_PUB_PORT, heartbeat_s=HEARTBEAT_S):
    """Connect the robot's signals and events, then start publishing, pinging and, with motion_poll, polling ALMotion; returns the three threads (the poller None without motion_poll) and the subscribers to keep alive."""
    publisher = PublisherThread(port=port)
    subscribers = connect(session, publisher, patterns)
    heartbeat = HeartbeatThread(session.service("ALMemory"), publisher, started, heartbeat_s)
    poller = MotionPollThread(session.service("ALMotion"), publisher, motion_poll, heartbeat_s) if motion_poll else None
    publisher.start()
    heartbeat.start()
    if poller:
        poller.start()
    return publisher, heartbeat, poller, subscribers


def main():
    try:
        import qi
    except ImportError:
        sys.stderr.write("event_publisher: qi not importable; exiting.\n")
        return 2

    try:
        patterns = read_patterns(EVENTS_FILE)
        motion_poll = read_motion_poll(MOTION_POLL_FILE)
    except (IOError, ValueError) as e:
        sys.stderr.write("event_publisher: cannot read the config: %s\n" % e)
        return 5

    naoqi_ip = os.environ.get("NAOQI_IP", "127.0.0.1")
    naoqi_port = int(os.environ.get("NAOQI_PORT", "9559"))
    app = qi.Application(["event_publisher", "--qi-url=tcp://%s:%d" % (naoqi_ip, naoqi_port)])
    try:
        app.start()
    except RuntimeError as e:
        sys.stderr.write("event_publisher: NAOqi unreachable at %s:%d: %s\n" % (naoqi_ip, naoqi_port, e))
        return 3

    session = app.session
    dropped = threading.Event()
    session.disconnected.connect(lambda reason: dropped.set())
    publisher, heartbeat, poller, kept = start(session, started=time.time(), patterns=patterns, motion_poll=motion_poll)
    sys.stderr.write("event_publisher: publishing on :%d from %s:%d\n" % (EVENT_PUB_PORT, naoqi_ip, naoqi_port))

    try:
        while not dropped.wait(1.0):
            pass
        sys.stderr.write("event_publisher: robot session dropped; exiting\n")
        return 4
    except KeyboardInterrupt:
        return 0
    finally:
        heartbeat.stop()
        if poller:
            poller.stop()
        publisher.stop()
        publisher.join(timeout=2.0)


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
