"""Module adapter registry. `build_module_adapters` returns a fresh dict
of `module_name -> adapter` for the dispatcher to use. Construct one set
of adapters per shim process; they hold mutable refs to pepper and the
task registry."""

from .base import GenericAdapter, StubAdapter
from .motion import ALMotionAdapter
from .memory import ALMemoryAdapter
from .posture import ALRobotPostureAdapter
from .laser import ALLaserAdapter
from .tts import ALTextToSpeechAdapter


def build_module_adapters(pepper, task_registry):
    """Construct the per-module adapter dict for one shim process."""
    tts = ALTextToSpeechAdapter(pepper, task_registry)
    return {
        # Modeled modules.
        "ALMotion": ALMotionAdapter(pepper, task_registry),
        "ALMemory": ALMemoryAdapter(pepper, task_registry),
        "ALRobotPosture": ALRobotPostureAdapter(pepper, task_registry),
        "ALLaser": ALLaserAdapter(pepper, task_registry),
        "ALTextToSpeech": tts,
        "ALAnimatedSpeech": tts,  # same surface; reuse the same instance

        # Pure-stub modules (every method returns the default).
        "ALAnimationPlayer": StubAdapter(default=None, task_registry=task_registry),
        "ALAutonomousLife": StubAdapter(
            default=None,
            overrides={"getState": "disabled"},
            task_registry=task_registry,
        ),
        "ALBasicAwareness": StubAdapter(
            default=None,
            overrides={"isEnabled": False},
            task_registry=task_registry,
        ),
        "ALFaceDetection": StubAdapter(default=None, task_registry=task_registry),
        "ALTracker": StubAdapter(
            default=None,
            overrides={"getMode": "Head"},
            task_registry=task_registry,
        ),
        "ALLandMarkDetection": StubAdapter(default=None, task_registry=task_registry),
        "ALSystem": StubAdapter(
            default=None,
            overrides={"systemVersion": "2.5.7.1"},
            task_registry=task_registry,
        ),
        "ALAudioPlayer": StubAdapter(
            default=None,
            overrides={"getCurrentPosition": 0.0},
            task_registry=task_registry,
        ),
        "ALAudioDevice": StubAdapter(
            default=None,
            overrides={"isAudioOutActing": False},
            task_registry=task_registry,
        ),
        "ALBattery": StubAdapter(
            default=None,
            overrides={"getBatteryCharge": 100.0},
            task_registry=task_registry,
        ),
        "ALBodyTemperature": StubAdapter(
            default=None,
            overrides={"getTemperatureDiagnosis": [0, []]},
            task_registry=task_registry,
        ),
    }


__all__ = ["build_module_adapters"]
