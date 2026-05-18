import json
import os
import warnings
from contextlib import contextmanager
from unittest.mock import patch
import pytest

# Allow the test to import naoqi_proxy directly.
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from naoqi_proxy import NaoqiClient, SimStubWarning


@contextmanager
def _fake_urlopen(body, headers=None, status=200):
    headers = headers or {}

    class FakeResponse:
        def __init__(self):
            self.status = status
            self.headers = headers

        def read(self):
            return json.dumps(body).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("urllib.request.urlopen", return_value=FakeResponse()) as mock:
        yield mock


def test_default_no_warning_on_stub_response():
    with _fake_urlopen({"result": None}, headers={"X-Sim-Stub": "1"}):
        client = NaoqiClient()  # default warn_on_stubs=False
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            client.ALMotion.wakeUp()
        sim_warnings = [w for w in recorded if issubclass(w.category, SimStubWarning)]
        assert sim_warnings == []


def test_opt_in_warning_on_stub_response():
    with _fake_urlopen({"result": None}, headers={"X-Sim-Stub": "1"}):
        client = NaoqiClient(warn_on_stubs=True)
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            client.ALMotion.wakeUp()
        sim_warnings = [w for w in recorded if issubclass(w.category, SimStubWarning)]
        assert len(sim_warnings) == 1
        assert "ALMotion.wakeUp" in str(sim_warnings[0].message)


def test_no_warning_when_header_absent():
    with _fake_urlopen({"result": None}, headers={}):
        client = NaoqiClient(warn_on_stubs=True)
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            client.ALMotion.move(0, 0, 0)
        sim_warnings = [w for w in recorded if issubclass(w.category, SimStubWarning)]
        assert sim_warnings == []


def test_env_var_enables_warning(monkeypatch):
    monkeypatch.setenv("NAOQI_SIM_WARN_STUBS", "1")
    with _fake_urlopen({"result": None}, headers={"X-Sim-Stub": "1"}):
        client = NaoqiClient()  # no explicit flag; env var should win
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            client.ALTracker.lookAt([0, 0, 0])
        sim_warnings = [w for w in recorded if issubclass(w.category, SimStubWarning)]
        assert len(sim_warnings) == 1


def test_error_filter_raises_on_stub():
    with _fake_urlopen({"result": None}, headers={"X-Sim-Stub": "1"}):
        client = NaoqiClient(warn_on_stubs=True)
        with warnings.catch_warnings():
            warnings.simplefilter("error", SimStubWarning)
            with pytest.raises(SimStubWarning):
                client.ALMotion.wakeUp()
                
def test_warning_points_at_caller_source_line():
    """Asserts the warning's reported filename is the caller's file, not naoqi_proxy.py."""
    with _fake_urlopen({"result": None}, headers={"X-Sim-Stub": "1"}):
        client = NaoqiClient(warn_on_stubs=True)
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            client.ALMotion.wakeUp()
        sim_warnings = [w for w in recorded if issubclass(w.category, SimStubWarning)]
        assert len(sim_warnings) == 1
        assert "test_sim_stub_warning.py" in sim_warnings[0].filename
        assert "naoqi_proxy.py" not in sim_warnings[0].filename
