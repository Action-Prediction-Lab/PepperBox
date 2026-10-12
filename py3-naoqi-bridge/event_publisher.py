# py3-naoqi-bridge/event_publisher.py (Python 2)
"""NAOqi behaviour signals and ALMemory events -> ZMQ PUB :5565, with a heartbeat each time the robot answers a ping."""
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


def read_patterns(path):
    """Event name patterns from the config file, one per line; blank lines and lines starting with # are skipped."""
    with open(path) as f:
        lines = [line.strip() for line in f]
    return [line for line in lines if line and not line.startswith("#")]


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


def start(session, started, patterns, port=EVENT_PUB_PORT, heartbeat_s=HEARTBEAT_S):
    """Connect the robot's signals and events, then start publishing and pinging; returns the two threads and the subscribers to keep alive."""
    publisher = PublisherThread(port=port)
    subscribers = connect(session, publisher, patterns)
    heartbeat = HeartbeatThread(session.service("ALMemory"), publisher, started, heartbeat_s)
    publisher.start()
    heartbeat.start()
    return publisher, heartbeat, subscribers


def main():
    try:
        import qi
    except ImportError:
        sys.stderr.write("event_publisher: qi not importable; exiting.\n")
        return 2

    try:
        patterns = read_patterns(EVENTS_FILE)
    except IOError as e:
        sys.stderr.write("event_publisher: cannot read %s: %s\n" % (EVENTS_FILE, e))
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
    publisher, heartbeat, kept = start(session, started=time.time(), patterns=patterns)
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
        publisher.stop()
        publisher.join(timeout=2.0)


if __name__ == "__main__":
    sys.exit(main())
