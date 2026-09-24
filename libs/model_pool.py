#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pools of pre-loaded models - neither Whisper nor the diarizer is thread-safe, so requests borrow one."""

import logging
import queue
import time
import traceback
from typing import Any

# Local imports
from libs import config, diarize, stt

logger = logging.getLogger(__name__)

# How long a request waits for a free model before the pool is declared exhausted.
MODEL_ACQUIRE_TIMEOUT = 120

# The diarizer gets a much shorter bound. Transcription is minutes of work, so waiting for it
# is reasonable; diarization is a fraction of realtime, so a wait this long means the pool is
# genuinely oversubscribed, and parking a WSGI thread for two minutes starves everything else,
# including the healthcheck.
DIARIZER_ACQUIRE_TIMEOUT = 30

MODEL_POOL: queue.Queue = queue.Queue()
DIARIZER_POOL: queue.Queue = queue.Queue()

# How many diarizers actually loaded. Zero with diarization switched on means loading failed,
# which is not the same as "all of them are busy" and must not cost a request the full timeout.
DIARIZERS_LOADED = 0


def init_model_pool(size: int | None = None) -> None:
    """Pre-load Whisper instances into the pool. Called once per process at startup.

    The size is read at call time rather than bound as a default argument, so a test or a
    caller that changes `config.MODEL_POOL_SIZE` is actually obeyed.
    """
    size = config.MODEL_POOL_SIZE if size is None else size
    logger.info("Initializing %d Whisper model instances...", size)
    for number in range(1, size + 1):
        start_time = time.monotonic()
        MODEL_POOL.put(stt.get_model())
        logger.info("Model #%d ready (%.2fs)", number, time.monotonic() - start_time)
    logger.info("Model pool ready: %d instances", MODEL_POOL.qsize())


def init_diarizer_pool(size: int | None = None) -> None:
    """Pre-load diarizer instances into their own pool, or do nothing when diarization is off.

    A separate queue rather than a second kind of entry in MODEL_POOL: that queue hands out
    whatever is at its head and has no notion of kind, so mixing the two would make every
    caller check what it got.
    """
    if not config.DIARIZE_ENABLED:
        logger.info("Diarization disabled (DIARIZE_ENABLED is false); no diarizer loaded")
        return

    global DIARIZERS_LOADED

    size = config.DIARIZE_POOL_SIZE if size is None else size
    logger.info("Initializing %d diarizer instances (%s)...", size, config.DIARIZE_MODEL)
    for number in range(1, size + 1):
        start_time = time.monotonic()
        try:
            DIARIZER_POOL.put(diarize.get_diarizer())
            DIARIZERS_LOADED += 1
        except Exception as exc:
            # An optional backend must fail optionally. Raising here would abort main(), and
            # under Gunicorn it would raise inside post_fork and boot-loop every worker, so a
            # missing diarization dependency would take transcription down with it. Leave the
            # pool empty instead: /api/diarize answers 503 and /api/stt keeps serving.
            logger.error(
                "Diarizer #%d failed to load, diarization will be unavailable: %s: %s\n%s",
                number,
                type(exc).__name__,
                exc,
                traceback.format_exc(),
            )
            return
        logger.info("Diarizer #%d ready (%.2fs)", number, time.monotonic() - start_time)
    logger.info("Diarizer pool ready: %d instances", DIARIZER_POOL.qsize())


def acquire_model(timeout: int = MODEL_ACQUIRE_TIMEOUT) -> Any:
    """Take a Whisper model out of the pool; raises queue.Empty when none frees up in time."""
    return MODEL_POOL.get(timeout=timeout)


def release_model(model: Any) -> None:
    """Return a Whisper model to the pool so the next request can use it."""
    MODEL_POOL.put(model)


def diarizer_ready() -> bool:
    """Whether a diarizer exists at all, as opposed to every one of them being busy.

    True as soon as one instance was loaded, or as soon as the pool holds anything, so a test
    that fills the pool directly is served without also setting the counter.
    """
    return DIARIZERS_LOADED > 0 or not DIARIZER_POOL.empty()


def acquire_diarizer(timeout: int = DIARIZER_ACQUIRE_TIMEOUT) -> Any:
    """Take a diarizer out of its pool; raises queue.Empty when none frees up in time."""
    return DIARIZER_POOL.get(timeout=timeout)


def release_diarizer(diarizer: Any) -> None:
    """Return a diarizer to its pool so the next request can use it."""
    DIARIZER_POOL.put(diarizer)


def get_pool_status() -> dict[str, Any]:
    """Report both pools: the configured sizes and how many instances are currently free."""
    status: dict[str, Any] = {
        "pool_size": config.MODEL_POOL_SIZE,
        "available": MODEL_POOL.qsize(),
        "diarize": config.DIARIZE_ENABLED,
    }
    if config.DIARIZE_ENABLED:
        status["diarize_pool_size"] = config.DIARIZE_POOL_SIZE
        status["diarize_available"] = DIARIZER_POOL.qsize()
    return status


def main():
    """No-op entry point: this module is imported for its pool helpers."""
    pass


if __name__ == "__main__":
    main()
