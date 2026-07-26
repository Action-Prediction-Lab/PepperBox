"""ALTextToSpeech adapter: qibullet has no audio backend, so `say` logs the phrase to stderr."""

import sys

from .base import GenericAdapter, stub


class ALTextToSpeechAdapter(GenericAdapter):

    @stub()
    def say(self, text):
        sys.stderr.write("[SIM-TTS] {}\n".format(text))
        return None

    @stub()
    def getAvailableLanguages(self):
        return ["English"]
