from unittest.mock import MagicMock
import pytest
from dispatcher import Dispatcher
from post_tasks import TaskRegistry
from adapters import build_module_adapters


def _dispatcher():
    # Create a mock with spec of known methods so hasattr works correctly.
    pepper = MagicMock(spec=[
        'move', 'moveToward', 'moveTo', 'stopMove', 'getPosition',
        'getAnglesPosition', 'setAngles', 'getRobotPosition',
        'wakeUp', 'robotIsWakeUp', 'setStiffnesses', 'setBreathConfig',
        'setBreathEnabled', 'setExternalCollisionProtectionEnabled',
        'getRobotConfig', 'goToPosture', 'getFrontLaserValue',
        'getLeftLaserValue', 'getRightLaserValue', 'insertData',
        'showLaser',
    ])
    registry = TaskRegistry()
    adapters = build_module_adapters(pepper, registry)
    return Dispatcher(adapters), pepper


def test_dispatch_returns_result_and_is_stub_false_for_real_method():
    d, pepper = _dispatcher()
    result, is_stub = d.dispatch("ALMotion", "move", [1.0, 0, 0], {})
    assert is_stub is False
    pepper.move.assert_called_once_with(1.0, 0.0, 0.0)


def test_dispatch_is_stub_true_for_stub_method():
    d, _ = _dispatcher()
    result, is_stub = d.dispatch("ALMotion", "wakeUp", [], {})
    assert result is None
    assert is_stub is True


def test_dispatch_unknown_module_raises_attribute_error():
    d, _ = _dispatcher()
    with pytest.raises(AttributeError, match="No adapter for module"):
        d.dispatch("ALNonExistent", "doStuff", [], {})


def test_dispatch_unknown_method_on_known_module_raises():
    d, _ = _dispatcher()
    with pytest.raises(AttributeError, match="has no method"):
        d.dispatch("ALMotion", "definitelyFake", [], {})


def test_dispatch_blocks_underscore_prefix():
    d, _ = _dispatcher()
    with pytest.raises(AttributeError, match="is private"):
        d.dispatch("ALMotion", "_secret", [], {})


def test_dispatch_blocks_loadrobot():
    d, _ = _dispatcher()
    with pytest.raises(AttributeError, match="is blocked"):
        d.dispatch("ALMotion", "loadRobot", [], {})


def test_dispatch_post_unwraps_target_method():
    d, pepper = _dispatcher()
    pepper.move.return_value = None
    result, is_stub = d.dispatch("ALMotion", "post", ["move", 1.0, 0, 0], {})
    assert isinstance(result, int)
    assert is_stub is False
    pepper.move.assert_called_once_with(1.0, 0.0, 0.0)


def test_dispatch_post_propagates_unknown_target():
    d, _ = _dispatcher()
    with pytest.raises(AttributeError, match="has no method"):
        d.dispatch("ALMotion", "post", ["nonExistent"], {})


def test_dispatch_post_with_empty_args_raises():
    d, _ = _dispatcher()
    with pytest.raises(AttributeError, match="post requires the target method name"):
        d.dispatch("ALMotion", "post", [], {})


def test_dispatch_post_of_stub_target_still_returns_is_stub_false():
    d, _ = _dispatcher()
    result, is_stub = d.dispatch("ALMotion", "post", ["wakeUp"], {})
    assert isinstance(result, int)
    assert is_stub is False


def test_dispatch_stub_module_returns_is_stub_true():
    d, _ = _dispatcher()
    result, is_stub = d.dispatch("ALAnimationPlayer", "runTag", ["wave"], {})
    assert result is None
    assert is_stub is True
