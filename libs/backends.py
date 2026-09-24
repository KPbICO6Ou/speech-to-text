#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Which module transcribes. Resolved at call time so STT_BACKEND is obeyed, not cached."""

import logging
from types import ModuleType

# Local imports
from libs import config, parakeet, stt

logger = logging.getLogger(__name__)

# Every value here exports the same four names with the same signatures - get_model,
# get_stt_bio, get_stt_segments and describe_backend - so callers resolve the MODULE and
# then call it by name. A dispatcher that resolved the function instead would silently
# defeat every test that patches `stt.get_stt_bio`.
TRANSCRIBERS: dict[str, ModuleType] = {"whisper": stt, "parakeet": parakeet}

DEFAULT_TRANSCRIBER = "whisper"


def transcriber_name() -> str:
    """The configured backend name, falling back to the default when it names nothing real."""
    name = config.STT_BACKEND
    if name in TRANSCRIBERS:
        return name
    logger.warning("STT_BACKEND=%s is not a known backend; using %s", name, DEFAULT_TRANSCRIBER)
    return DEFAULT_TRANSCRIBER


def transcriber() -> ModuleType:
    """The module that transcribes for this deployment."""
    return TRANSCRIBERS[transcriber_name()]


def main():
    """No-op entry point: this module is imported for its dispatch helpers."""
    pass


if __name__ == "__main__":
    main()
