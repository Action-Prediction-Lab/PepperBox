"""ALTextToSpeech adapter. qibullet has no audio backend. Calls to .say
log the requested phrase to stderr so a developer watching the shim's
docker logs sees the intended utterance."""

import sys

from .base import GenericAdapter, stub


class ALTextToSpeechAdapter(GenericAdapter):

    @stub()
    def say(self, text):
        sys.stderr.write("[SIM-TTS] {}\n".format(text))
        return None

    @stub(default=["English"])
    def getAvailableLanguages(self):
        return ["English"]
