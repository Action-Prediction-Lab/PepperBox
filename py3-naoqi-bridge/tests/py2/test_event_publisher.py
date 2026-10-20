"""Tests for the event publisher: patterns, message building, the robot signal and event wiring and the ZMQ stream."""
import json
import os
import shutil
import tempfile
import threading
import time
import unittest

import zmq

from event_publisher import MOTION_POLL_FILE, HeartbeatThread, MotionPollThread, PublisherThread, connect, event_message, read_motion_poll, read_patterns, start


class FakeSignal(object):
    """A qi signal whose callbacks the test fires by hand; each connection is written to the shared call log."""

    def __init__(self, log):
        self.callbacks = []
        self.log = log

    def connect(self, callback):
        self.log.append("connect")
        self.callbacks.append(callback)
        return len(self.callbacks)

    def fire(self, *args):
        for callback in self.callbacks:
            callback(*args)


class FakeSubscriber(object):
    def __init__(self, log):
        self.signal = FakeSignal(log)


class FakeMemory(object):
    """ALMemory with a declared event list, event subscribers and a ping whose answer the test sets."""

    def __init__(self, log=None, events=()):
        self.events = list(events)
        self.subscribers = {}
        self.log = [] if log is None else log
        self.answer = lambda: True

    def getEventList(self):
        return list(self.events)

    def subscriber(self, event):
        subscriber = FakeSubscriber(self.log)
        self.subscribers.setdefault(event, []).append(subscriber)
        return subscriber

    def fire(self, event, value):
        for subscriber in self.subscribers.get(event, []):
            subscriber.signal.fire(value)

    def ping(self):
        self.log.append("ping")
        return self.answer()


class FakeBehaviorManager(object):
    def __init__(self, log):
        self.behaviorStarted = FakeSignal(log)
        self.behaviorStopped = FakeSignal(log)


class FakeSession(object):
    """A qi session serving the two NAOqi modules the publisher listens to, with one call log for both."""

    def __init__(self, events=()):
        self.log = []
        self.memory = FakeMemory(self.log, events)
        self.behavior_manager = FakeBehaviorManager(self.log)

    def service(self, name):
        return {"ALMemory": self.memory, "ALBehaviorManager": self.behavior_manager}[name]


class RecordingPublisher(object):
    def __init__(self):
        self.messages = []

    def enqueue(self, message):
        self.messages.append(message)

    def sent(self):
        """The topic and value of every message, in order."""
        return [(topic, payload["value"]) for topic, payload in self.messages]


class PatternTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_patterns_are_read_one_per_line_without_blanks_or_comments(self):
        """Blank lines and lines starting with # are skipped, and surrounding spaces are stripped."""
        path = os.path.join(self.dir, "events.txt")
        with open(path, "w") as f:
            f.write("*\n\n# a note\n  AutonomousLife/*  \n")
        self.assertEqual(read_patterns(path), ["*", "AutonomousLife/*"])


class MessageTests(unittest.TestCase):
    def test_a_value_json_cannot_encode_is_sent_as_its_repr(self):
        """An object or a byte string that is not UTF-8 becomes its repr, so the message still goes out."""
        thing = object()
        self.assertEqual(event_message("Some/Event", thing, 1.0)[1]["value"], repr(thing))
        self.assertEqual(event_message("Some/Event", "\xff", 1.0)[1]["value"], repr("\xff"))


class ConnectTests(unittest.TestCase):
    def test_behaviour_starts_and_stops_are_forwarded_with_their_paths(self):
        """Every behaviour start and stop is forwarded with its path."""
        session = FakeSession()
        publisher = RecordingPublisher()
        connect(session, publisher, ["*"])
        session.behavior_manager.behaviorStarted.fire("animations/Stand/Gestures/Me_8")
        session.behavior_manager.behaviorStarted.fire("robot-page/behavior_1")
        session.behavior_manager.behaviorStopped.fire("animations/Stand/Gestures/Me_8")
        self.assertEqual(publisher.sent(), [
            ("ALBehaviorManager.behaviorStarted", "animations/Stand/Gestures/Me_8"),
            ("ALBehaviorManager.behaviorStarted", "robot-page/behavior_1"),
            ("ALBehaviorManager.behaviorStopped", "animations/Stand/Gestures/Me_8")])
        for _, payload in publisher.messages:
            self.assertIsInstance(payload["t"], float)

    def test_matching_events_are_forwarded_with_their_raw_values(self):
        """Events matching the patterns are forwarded with every value NAOqi raises; others are never subscribed."""
        session = FakeSession(events=["ALTextToSpeech/TextStarted", "AutonomousLife/State", "PeoplePerception/PeopleList"])
        publisher = RecordingPublisher()
        connect(session, publisher, ["ALTextToSpeech/*", "AutonomousLife/State"])
        self.assertNotIn("PeoplePerception/PeopleList", session.memory.subscribers)
        session.memory.fire("ALTextToSpeech/TextStarted", 1)
        session.memory.fire("ALTextToSpeech/TextStarted", 0)
        session.memory.fire("AutonomousLife/State", "solitary")
        self.assertEqual(publisher.sent(), [
            ("ALTextToSpeech/TextStarted", 1),
            ("ALTextToSpeech/TextStarted", 0),
            ("AutonomousLife/State", "solitary")])

    def test_an_event_declared_later_is_subscribed(self):
        """An event an app declares after the start is announced by KeyAdded and then forwarded."""
        session = FakeSession()
        publisher = RecordingPublisher()
        connect(session, publisher, ["*"])
        session.memory.events.append("App/NewEvent")
        session.memory.fire("ALMemory/KeyAdded", "App/NewEvent")
        session.memory.fire("App/NewEvent", 7)
        self.assertEqual(publisher.sent(), [("App/NewEvent", 7)])

    def test_a_data_key_added_later_is_not_subscribed(self):
        """KeyAdded also announces data keys, which are not in the event list and are left alone."""
        session = FakeSession()
        connect(session, RecordingPublisher(), ["*"])
        session.memory.fire("ALMemory/KeyAdded", "App/SomeData")
        self.assertNotIn("App/SomeData", session.memory.subscribers)

    def test_a_removed_event_is_subscribed_again_when_declared_again(self):
        """KeyRemoved forgets the subscription, so a second declaration subscribes afresh."""
        session = FakeSession(events=["App/Event"])
        kept = connect(session, RecordingPublisher(), ["*"])
        session.memory.fire("ALMemory/KeyRemoved", "App/Event")
        self.assertNotIn("App/Event", kept["events"])
        session.memory.fire("ALMemory/KeyAdded", "App/Event")
        self.assertEqual(len(session.memory.subscribers["App/Event"]), 2)
        self.assertIn("App/Event", kept["events"])

    def test_returns_the_subscribers_to_keep_alive(self):
        """The event subscribers and the two key watchers are returned, because a dropped subscriber object ends its subscription."""
        session = FakeSession(events=["ALTextToSpeech/TextStarted", "AutonomousLife/State"])
        kept = connect(session, RecordingPublisher(), ["*"])
        self.assertEqual(sorted(kept["events"]), ["ALTextToSpeech/TextStarted", "AutonomousLife/State"])
        self.assertEqual(len(kept["watchers"]), 2)
        self.assertEqual(kept["watchers"], session.memory.subscribers["ALMemory/KeyAdded"] + session.memory.subscribers["ALMemory/KeyRemoved"])


class HeartbeatTests(unittest.TestCase):
    def run_heartbeat(self, memory, seconds=0.2):
        """Run a heartbeat thread against memory for a while and return what it enqueued."""
        publisher = RecordingPublisher()
        thread = HeartbeatThread(memory, publisher, started=42.0, heartbeat_s=0.01)
        thread.start()
        time.sleep(seconds)
        thread.stop()
        thread.join(timeout=1.0)
        return publisher.messages

    def test_each_answer_from_the_robot_is_a_heartbeat_with_the_start_time(self):
        """Every ping the robot answers is followed by one heartbeat carrying its time and the publisher's start time."""
        memory = FakeMemory()
        messages = self.run_heartbeat(memory)
        self.assertTrue(messages)
        self.assertEqual(len(messages), memory.log.count("ping"))
        for topic, payload in messages:
            self.assertEqual((topic, payload["started"]), ("heartbeat", 42.0))
            self.assertIsInstance(payload["t"], float)

    def test_no_heartbeat_while_the_robot_does_not_answer(self):
        """A ping that never returns, as on a link that silently drops the robot's packets, stops the heartbeats."""
        unblock = threading.Event()
        memory = FakeMemory()
        memory.answer = unblock.wait
        try:
            self.assertEqual(self.run_heartbeat(memory), [])
        finally:
            unblock.set()

    def test_a_failed_ping_is_skipped_and_pinging_goes_on(self):
        """A ping that raises gives no heartbeat, and the next answer gives one."""
        memory = FakeMemory()
        answers = iter([RuntimeError("no route to robot")])

        def answer():
            error = next(answers, None)
            if error:
                raise error
            return True

        memory.answer = answer
        messages = self.run_heartbeat(memory)
        self.assertTrue(messages)
        self.assertEqual(len(messages), memory.log.count("ping") - 1)


class FakeMotion(object):
    """Fake ALMotion whose task lists and angles follow scripts, repeating the last entry; it raises a script entry that is an exception."""

    def __init__(self, tasks, angles=None):
        self.tasks = list(tasks)
        self.angles = list(angles or [[0.0, 0.0]])
        self.calls = []

    def _next(self, script):
        value = script.pop(0) if len(script) > 1 else script[0]
        if isinstance(value, Exception):
            raise value
        return value

    def getBodyNames(self, names):
        self.calls.append(("getBodyNames", names))
        return ["HeadYaw", "HeadPitch"]

    def getTaskList(self):
        self.calls.append(("getTaskList",))
        return self._next(self.tasks)

    def getAngles(self, names, use_sensors):
        self.calls.append(("getAngles", list(names), use_sensors))
        return self._next(self.angles)


POLLING = {"poll_interval_s": 0.005, "ndigits": 3, "getAngles": {"names": "Body", "useSensors": True}}


class TimedMotion(object):
    """Fake ALMotion whose task list changes on every read; records when each read starts."""

    def __init__(self):
        self.reads = []

    def getTaskList(self):
        self.reads.append(time.time())
        return [["Idle", len(self.reads)]]


class SlowFirstMotion(object):
    """Fake ALMotion whose first task list read takes 0.1 s; records when each read starts."""

    def __init__(self):
        self.reads = []

    def getTaskList(self):
        self.reads.append(time.time())
        if len(self.reads) == 1:
            time.sleep(0.1)
        return []


class MotionPollTests(unittest.TestCase):
    def run_poller(self, motion, config=POLLING, seconds=0.15, heartbeat_s=1.0):
        """Run a poll thread against motion for a while and return what it enqueued."""
        publisher = RecordingPublisher()
        thread = MotionPollThread(motion, publisher, config, heartbeat_s)
        thread.start()
        time.sleep(seconds)
        thread.stop()
        thread.join(timeout=1.0)
        return publisher

    def test_the_task_list_is_published_each_time_it_changes(self):
        """The poller does not publish a task list equal to the previous one again within a heartbeat."""
        animation = ["angleInterpolationBezier", 7]
        motion = FakeMotion(tasks=[[], [animation], [animation], [animation, ["LookAt", 8]], []])
        sent = [value for topic, value in self.run_poller(motion).sent() if topic == "ALMotion.getTaskList"]
        self.assertEqual(sent, [[], [animation], [animation, ["LookAt", 8]], []])

    def test_angles_are_published_rounded_with_the_joint_names_when_they_change(self):
        """The poller reads the angles of the configured names and sensors, rounds them, and publishes them only when a rounded angle changes."""
        motion = FakeMotion(tasks=[[]], angles=[[0.12341, 1.0], [0.12344, 1.0], [0.1250, 1.0]])
        sent = [value for topic, value in self.run_poller(motion).sent() if topic == "ALMotion.getAngles"]
        self.assertEqual(sent, [{"names": ["HeadYaw", "HeadPitch"], "useSensors": True, "angles": [0.123, 1.0]},
                                {"names": ["HeadYaw", "HeadPitch"], "useSensors": True, "angles": [0.125, 1.0]}])
        self.assertIn(("getBodyNames", "Body"), motion.calls)
        self.assertIn(("getAngles", ["HeadYaw", "HeadPitch"], True), motion.calls)

    def test_without_getangles_in_the_config_only_the_task_list_is_polled(self):
        motion = FakeMotion(tasks=[[["angleInterpolationBezier", 7]]])
        publisher = self.run_poller(motion, config={"poll_interval_s": 0.005})
        self.assertEqual([topic for topic, _ in publisher.sent()], ["ALMotion.getTaskList"])
        self.assertEqual([call for call in motion.calls if call[0] != "getTaskList"], [])

    def test_unchanged_state_is_published_again_every_heartbeat(self):
        """A subscriber that joins after the last change gets the task list and angles within a heartbeat."""
        motion = FakeMotion(tasks=[[["Idle", 3]]], angles=[[0.1, 0.2]])
        topics = [topic for topic, _ in self.run_poller(motion, seconds=0.2, heartbeat_s=0.04).sent()]
        self.assertGreaterEqual(topics.count("ALMotion.getTaskList"), 4)
        self.assertGreaterEqual(topics.count("ALMotion.getAngles"), 4)

    def test_a_failed_poll_is_skipped_and_polling_goes_on(self):
        """A poll that raises publishes nothing, and the next poll publishes again."""
        motion = FakeMotion(tasks=[RuntimeError("no route to robot"), [["angleInterpolationBezier", 7]]])
        sent = [value for topic, value in self.run_poller(motion).sent() if topic == "ALMotion.getTaskList"]
        self.assertEqual(sent, [[["angleInterpolationBezier", 7]]])

    def test_each_message_carries_its_poll_time(self):
        """The poller publishes a task list that changes on every read once per poll and stamps each message within 10 ms of its read."""
        motion = TimedMotion()
        messages = [payload for topic, payload in self.run_poller(motion, config={"poll_interval_s": 0.01}).messages if topic == "ALMotion.getTaskList"]
        self.assertGreater(len(messages), 5)
        for read, payload in zip(motion.reads, messages):
            self.assertTrue(read <= payload["t"] <= read + 0.01)

    def test_getangles_without_ndigits_is_refused(self):
        path = os.path.join(tempfile.mkdtemp(), "motion_poll.json")
        with open(path, "w") as f:
            json.dump({"poll_interval_s": 0.02, "getAngles": {"names": "Body", "useSensors": True}}, f)
        with self.assertRaises(ValueError):
            read_motion_poll(path)

    def test_after_a_slow_poll_the_schedule_restarts_from_now(self):
        """After a poll that overruns its interval, the poller polls again at once and then at the normal interval, with no burst of catch-up polls."""
        motion = SlowFirstMotion()
        self.run_poller(motion, config={"poll_interval_s": 0.01}, seconds=0.25)
        gaps = [b - a for a, b in zip(motion.reads[1:], motion.reads[2:])]
        self.assertGreater(len(gaps), 5)
        self.assertLessEqual(sum(1 for gap in gaps if gap < 0.003), 1)

    def test_the_shipped_config_gives_every_setting_the_poller_reads(self):
        config = read_motion_poll(MOTION_POLL_FILE)
        self.assertEqual(sorted(config), ["getAngles", "ndigits", "poll_interval_s"])
        self.assertGreater(config["poll_interval_s"], 0)
        self.assertIsInstance(config["ndigits"], int)
        self.assertEqual(sorted(config["getAngles"]), ["names", "useSensors"])


class StartTests(unittest.TestCase):
    def test_the_robot_is_pinged_only_after_its_signals_and_events_are_connected(self):
        """The first ping comes after the last signal or event is connected, so a heartbeat always means events can arrive."""
        session = FakeSession(events=["ALTextToSpeech/TextStarted", "ALTextToSpeech/TextDone"])
        publisher, heartbeat, _, _ = start(session, started=1.0, patterns=["*"], port=15566, heartbeat_s=0.01)
        try:
            time.sleep(0.1)
        finally:
            heartbeat.stop()
            publisher.stop()
            heartbeat.join(timeout=1.0)
            publisher.join(timeout=1.0)
        self.assertIn("ping", session.log)
        last_connect = max(i for i, entry in enumerate(session.log) if entry == "connect")
        self.assertGreater(session.log.index("ping"), last_connect)


class StreamTests(unittest.TestCase):
    PORT = 15565

    def setUp(self):
        self.thread = PublisherThread(port=self.PORT)
        self.thread.start()
        self.sub = zmq.Context.instance().socket(zmq.SUB)
        self.sub.setsockopt(zmq.RCVTIMEO, 1000)
        self.sub.connect("tcp://localhost:%d" % self.PORT)

    def tearDown(self):
        self.sub.close()
        self.thread.stop()
        self.thread.join(timeout=2.0)

    def test_messages_arrive_as_topic_and_json(self):
        """An enqueued message is sent as a topic frame and a JSON frame, and a subscription to a NAOqi prefix receives its events."""
        self.sub.setsockopt(zmq.SUBSCRIBE, b"ALTextToSpeech/")
        time.sleep(0.2)
        self.thread.enqueue(("ALTextToSpeech/TextStarted", {"t": 1.5, "value": 1}))
        received_topic, body = self.sub.recv_multipart()
        self.assertEqual((received_topic, json.loads(body)), (b"ALTextToSpeech/TextStarted", {"t": 1.5, "value": 1}))


if __name__ == "__main__":
    unittest.main()
