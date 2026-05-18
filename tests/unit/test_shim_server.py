from unittest.mock import MagicMock
import pytest
from shim_server import create_app
from post_tasks import TaskRegistry
from adapters import build_module_adapters


def _make_pepper():
    """Return a MagicMock that mimics PepperVirtual's attribute surface."""
    pepper = MagicMock(spec=[])
    pepper.move = MagicMock(return_value=None)
    pepper.getPosition = MagicMock(return_value=(0.0, 0.0, 0.0))
    pepper.getAnglesPosition = MagicMock(return_value=[0.0, 0.0])
    pepper.goToPosture = MagicMock(return_value=True)
    pepper.showLaser = MagicMock(return_value=None)
    pepper.getFrontLaserValue = MagicMock(return_value=[3.0])
    pepper.getLeftLaserValue = MagicMock(return_value=[3.0])
    pepper.getRightLaserValue = MagicMock(return_value=[3.0])
    return pepper


def _client():
    pepper = _make_pepper()
    registry = TaskRegistry()
    adapters = build_module_adapters(pepper, registry)
    app = create_app(adapters)
    return app.test_client(), pepper


def test_post_call_returns_200_for_real_method():
    client, pepper = _client()
    resp = client.post("/api/call", json={
        "module": "ALMotion", "method": "move",
        "args": [1.0, 0, 0], "kwargs": {},
    })
    assert resp.status_code == 200
    assert resp.get_json() == {"result": None}
    assert resp.headers.get("X-Sim-Stub") is None
    pepper.move.assert_called_once_with(1.0, 0.0, 0.0)


def test_post_call_sets_xsimstub_header_for_stub():
    client, _ = _client()
    resp = client.post("/api/call", json={
        "module": "ALMotion", "method": "wakeUp",
        "args": [], "kwargs": {},
    })
    assert resp.status_code == 200
    assert resp.get_json() == {"result": None}
    assert resp.headers.get("X-Sim-Stub") == "1"


def test_unknown_module_returns_500():
    client, _ = _client()
    resp = client.post("/api/call", json={
        "module": "ALNonExistent", "method": "doStuff",
        "args": [], "kwargs": {},
    })
    assert resp.status_code == 500
    assert "No adapter for module" in resp.get_json()["error"]


def test_unknown_method_returns_500():
    client, _ = _client()
    resp = client.post("/api/call", json={
        "module": "ALMotion", "method": "definitelyFake",
        "args": [], "kwargs": {},
    })
    assert resp.status_code == 500
    assert "has no method" in resp.get_json()["error"]


def test_missing_module_key_returns_400():
    client, _ = _client()
    resp = client.post("/api/call", json={"method": "move", "args": []})
    assert resp.status_code == 400
    assert "module" in resp.get_json()["error"]


def test_missing_method_key_returns_400():
    client, _ = _client()
    resp = client.post("/api/call", json={"module": "ALMotion", "args": []})
    assert resp.status_code == 400
    assert "method" in resp.get_json()["error"]


def test_adapter_exception_returns_500():
    client, pepper = _client()
    pepper.move.side_effect = RuntimeError("pybullet exploded")
    resp = client.post("/api/call", json={
        "module": "ALMotion", "method": "move", "args": [0, 0, 0],
    })
    assert resp.status_code == 500
    assert "pybullet exploded" in resp.get_json()["error"]


def test_post_dispatch_returns_task_id():
    client, _ = _client()
    resp = client.post("/api/call", json={
        "module": "ALMotion", "method": "post",
        "args": ["wakeUp"], "kwargs": {},
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert isinstance(body["result"], int)
    assert body["result"] >= 1


def test_call_with_omitted_kwargs_uses_empty_dict_default():
    """Verifies the route's data.get('kwargs', {}) default. Callers that
    don't send a kwargs key (e.g. curl users) still work."""
    client, pepper = _client()
    resp = client.post("/api/call", json={
        "module": "ALMotion", "method": "move",
        "args": [1.0, 0, 0],
    })
    assert resp.status_code == 200
    pepper.move.assert_called_once_with(1.0, 0.0, 0.0)
