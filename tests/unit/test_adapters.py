from unittest.mock import MagicMock
import pytest
from adapters.base import GenericAdapter, StubAdapter, stub
from post_tasks import TaskRegistry


# --- @stub decorator ---

def test_stub_decorator_marks_function():
    @stub()
    def f():
        return 7
    assert f() == 7
    assert getattr(f, "_sim_stub", False) is True


def test_stub_decorator_preserves_name():
    @stub()
    def my_method():
        pass
    assert my_method.__name__ == "my_method"


# --- GenericAdapter ---

def test_generic_falls_through_to_pepper_for_existing_method():
    pepper = MagicMock()
    pepper.someMethod.return_value = "qibullet-result"
    adapter = GenericAdapter(pepper, TaskRegistry())
    assert adapter.someMethod("arg") == "qibullet-result"
    pepper.someMethod.assert_called_once_with("arg")


def test_generic_raises_for_missing_pepper_method():
    pepper = MagicMock(spec=[])  # spec=[] makes hasattr return False for everything
    adapter = GenericAdapter(pepper, TaskRegistry())
    with pytest.raises(AttributeError, match="PepperVirtual has no method"):
        adapter.nonExistent


def test_generic_blocks_underscore_prefix():
    pepper = MagicMock()
    adapter = GenericAdapter(pepper, TaskRegistry())
    with pytest.raises(AttributeError, match="is private"):
        adapter._secret


def test_generic_blocks_loadrobot():
    pepper = MagicMock()
    pepper.loadRobot = MagicMock()  
    adapter = GenericAdapter(pepper, TaskRegistry())
    with pytest.raises(AttributeError, match="is blocked"):
        adapter.loadRobot


def test_generic_post_runs_target_and_returns_task_id():
    pepper = MagicMock()
    pepper.someMethod.return_value = "done"
    registry = TaskRegistry()
    adapter = GenericAdapter(pepper, registry)
    task_id = adapter.post("someMethod", "arg")
    assert isinstance(task_id, int)
    assert registry._tasks[task_id]["result"] == "done"
    pepper.someMethod.assert_called_once_with("arg")


def test_generic_post_propagates_unknown_target():
    pepper = MagicMock(spec=[])
    adapter = GenericAdapter(pepper, TaskRegistry())
    with pytest.raises(AttributeError):
        adapter.post("nonExistent", "arg")


def test_generic_subclass_method_takes_precedence_over_fallthrough():
    """If a subclass defines a method, it must be called instead of falling
    through to pepper. This protects against accidentally using
    __getattribute__ instead of __getattr__ in the base class."""

    class MySubclass(GenericAdapter):
        def myMethod(self):
            return "from-subclass"

    pepper = MagicMock()
    pepper.myMethod.return_value = "from-pepper"
    adapter = MySubclass(pepper, TaskRegistry())

    assert adapter.myMethod() == "from-subclass"
    pepper.myMethod.assert_not_called()


def test_generic_post_forwards_multiple_args_and_kwargs():
    """post must forward arbitrary positional and keyword arguments to the
    target. Live callers pass complex payloads (e.g. lookAt takes a point
    list, two floats, and a bool)."""
    pepper = MagicMock()
    adapter = GenericAdapter(pepper, TaskRegistry())
    adapter.post("multiArgMethod", 1, "two", 3.0, flag=True, mode="x")
    pepper.multiArgMethod.assert_called_once_with(1, "two", 3.0, flag=True, mode="x")


# --- StubAdapter ---

def test_stub_adapter_returns_default():
    adapter = StubAdapter(default=None, task_registry=TaskRegistry())
    assert adapter.anyMethod("ignored") is None


def test_stub_adapter_marks_returned_callable():
    adapter = StubAdapter(default=None, task_registry=TaskRegistry())
    stub_callable = adapter.anyMethod
    assert getattr(stub_callable, "_sim_stub", False) is True


def test_stub_adapter_uses_per_method_override():
    adapter = StubAdapter(
        default=None,
        overrides={"getMode": "Head"},
        task_registry=TaskRegistry(),
    )
    assert adapter.getMode() == "Head"
    assert adapter.someOtherMethod() is None


def test_stub_adapter_post_runs_stub_target():
    registry = TaskRegistry()
    adapter = StubAdapter(default=None, task_registry=registry)
    task_id = adapter.post("anyMethod", "arg")
    assert isinstance(task_id, int)
    assert registry._tasks[task_id]["result"] is None


# --- ALMotionAdapter ---

from adapters.motion import ALMotionAdapter


def _motion_adapter():
    return ALMotionAdapter(MagicMock(), TaskRegistry())


def test_motion_move_passes_floats():
    adapter = _motion_adapter()
    adapter.move("1.5", "0", "0.5")
    adapter._pepper.move.assert_called_once_with(1.5, 0.0, 0.5)


def test_motion_movetoward_scales_by_max_velocity():
    from qibullet.base_controller import PepperBaseController as PBC
    adapter = _motion_adapter()
    adapter.moveToward(0.5, 0, 0.5)
    adapter._pepper.move.assert_called_once_with(
        0.5 * PBC.MAX_LINEAR_VELOCITY,
        0.0 * PBC.MAX_LINEAR_VELOCITY,
        0.5 * PBC.MAX_ANGULAR_VELOCITY,
    )


def test_motion_moveto_forces_async():
    adapter = _motion_adapter()
    adapter.moveTo(1.0, 0.0, 0.0)
    adapter._pepper.moveTo.assert_called_once_with(1.0, 0.0, 0.0, _async=True)


def test_motion_stopmove_zeros_velocity():
    adapter = _motion_adapter()
    adapter.stopMove()
    adapter._pepper.stopMove.assert_called_once_with()
    adapter._pepper.move.assert_called_once_with(0, 0, 0)


def test_motion_getrobotposition_returns_list():
    adapter = _motion_adapter()
    adapter._pepper.getPosition.return_value = (1.0, 2.0, 0.5)
    result = adapter.getRobotPosition(True)
    assert result == [1.0, 2.0, 0.5]
    adapter._pepper.getPosition.assert_called_once_with()


def test_motion_getangles_wraps_scalar_to_list():
    adapter = _motion_adapter()
    adapter._pepper.getAnglesPosition.return_value = 0.42  # scalar from qibullet
    result = adapter.getAngles("HeadYaw", True)
    assert result == [0.42]


def test_motion_getangles_preserves_list():
    adapter = _motion_adapter()
    adapter._pepper.getAnglesPosition.return_value = [0.1, 0.2]
    result = adapter.getAngles(["HeadYaw", "HeadPitch"], True)
    assert result == [0.1, 0.2]


def test_motion_setangles_passes_through():
    adapter = _motion_adapter()
    adapter.setAngles(["HeadYaw"], [0.3], 0.1)
    adapter._pepper.setAngles.assert_called_once_with(["HeadYaw"], [0.3], 0.1)


def test_motion_angleinterpolation_calls_setangles():
    adapter = _motion_adapter()
    adapter.angleInterpolation(["RHand"], [0.5], [2.0], True)
    adapter._pepper.setAngles.assert_called_once_with(["RHand"], [0.5], 0.5)


def test_motion_wakeup_is_stub():
    adapter = _motion_adapter()
    assert adapter.wakeUp() is None
    assert getattr(type(adapter).wakeUp, "_sim_stub", False) is True


def test_motion_robotiswakeup_returns_true():
    adapter = _motion_adapter()
    assert adapter.robotIsWakeUp() is True


def test_motion_setstiffnesses_is_stub_no_op():
    adapter = _motion_adapter()
    assert adapter.setStiffnesses("Head", 0.5) is None
    adapter._pepper.setStiffnesses.assert_not_called()


def test_motion_setbreathconfig_is_stub_no_op():
    adapter = _motion_adapter()
    assert adapter.setBreathConfig([["Bpm", 15.0], ["Amplitude", 0.99]]) is None
    adapter._pepper.setBreathConfig.assert_not_called()


def test_motion_setbreathenabled_is_stub_no_op():
    adapter = _motion_adapter()
    assert adapter.setBreathEnabled("Legs", True) is None
    adapter._pepper.setBreathEnabled.assert_not_called()


def test_motion_setexternalcollisionprotectionenabled_is_stub_no_op():
    adapter = _motion_adapter()
    assert adapter.setExternalCollisionProtectionEnabled("RArm", False) is None
    adapter._pepper.setExternalCollisionProtectionEnabled.assert_not_called()


def test_motion_getrobotconfig_returns_empty_list():
    adapter = _motion_adapter()
    assert adapter.getRobotConfig() == []


def test_motion_wait_delegates_to_registry():
    pepper = MagicMock()
    registry = TaskRegistry()
    adapter = ALMotionAdapter(pepper, registry)
    fake_id = registry.submit_sync(lambda: None, (), {})
    assert adapter.wait(fake_id, 5000) is True
    assert adapter.wait(99999, 5000) is False


# --- ALMemoryAdapter ---

from adapters.memory import ALMemoryAdapter


def _memory_adapter():
    return ALMemoryAdapter(MagicMock(), TaskRegistry())


def test_memory_getdata_front_sonar_returns_min_laser():
    adapter = _memory_adapter()
    adapter._pepper.getFrontLaserValue.return_value = [3.0, 2.5, 4.0]
    result = adapter.getData("Device/SubDeviceList/Platform/Front/Sonar/Sensor/Value")
    assert result == 2.5


def test_memory_getdata_back_sonar_returns_min_of_left_plus_right():
    adapter = _memory_adapter()
    adapter._pepper.getLeftLaserValue.return_value = [3.0, 2.8]
    adapter._pepper.getRightLaserValue.return_value = [2.4, 3.5]
    result = adapter.getData("Device/SubDeviceList/Platform/Back/Sonar/Sensor/Value")
    assert result == 2.4


def test_memory_getdata_front_sonar_empty_returns_max_range():
    adapter = _memory_adapter()
    adapter._pepper.getFrontLaserValue.return_value = []
    result = adapter.getData("Device/SubDeviceList/Platform/Front/Sonar/Sensor/Value")
    assert result == 3.0


def test_memory_getdata_back_sonar_empty_returns_max_range():
    adapter = _memory_adapter()
    adapter._pepper.getLeftLaserValue.return_value = []
    adapter._pepper.getRightLaserValue.return_value = []
    result = adapter.getData("Device/SubDeviceList/Platform/Back/Sonar/Sensor/Value")
    assert result == 3.0


def test_memory_getdata_laser_front_returns_raw_array():
    adapter = _memory_adapter()
    adapter._pepper.getFrontLaserValue.return_value = [1.0, 2.0, 3.0]
    result = adapter.getData("Device/SubDeviceList/Platform/Laser/Front/Sensor/Value")
    assert result == [1.0, 2.0, 3.0]


def test_memory_getdata_landmark_returns_empty_detection():
    adapter = _memory_adapter()
    result = adapter.getData("LandmarkDetected", 0)
    assert result == [0, [], 0]


def test_memory_getdata_unknown_key_returns_none():
    adapter = _memory_adapter()
    assert adapter.getData("SomeRandomKey") is None


def test_memory_getlistdata_routes_each_key():
    adapter = _memory_adapter()
    adapter._pepper.getFrontLaserValue.return_value = [2.0]
    result = adapter.getListData([
        "Device/SubDeviceList/Platform/Front/Sonar/Sensor/Value",
        "UnknownKey",
    ])
    assert result == [2.0, None]


def test_memory_insertdata_is_stub():
    adapter = _memory_adapter()
    assert adapter.insertData("key", "value") is None
    adapter._pepper.insertData.assert_not_called()
