#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test fixtures: stub the model backends before stt_server is imported, expose a Flask test client.

Helpers live in tests/helpers.py. Importing them from here instead would make a test module do
`from tests.conftest import ...`, which executes this file a SECOND time under a second name and
leaves two rival sets of stubs in sys.modules.
"""

import os
import queue
import sys
import types

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import libs  # noqa: E402  (the real package; only the backend modules below are replaced)


def fake_get_model():
    """Stand in for stt.get_model() - the tests never load real Whisper weights."""
    return object()


def fake_get_stt_bio(bio, model=None, device=None, language=None):
    """Stand in for stt.get_stt_bio() with a fixed transcription."""
    return "stub transcription"


def fake_get_diarizer(model_id=None):
    """Stand in for diarize.get_diarizer() - the tests never load real diarization weights."""
    return object()


def fake_diarize_wav(bio, diarizer=None, threshold=None):
    """Stand in for diarize.diarize_wav() with two fixed, overlapping speaker turns."""
    return [
        {"speaker": 0, "start": 0.0, "end": 1.2},
        {"speaker": 1, "start": 1.0, "end": 2.5},
    ]


# Replace both backend modules so the tests need neither torch, whisper, soundfile nor
# transformers installed. Must run before stt_server (and therefore libs.model_pool) is
# imported anywhere.
fake_stt = types.ModuleType("libs.stt")
fake_stt.get_model = fake_get_model
fake_stt.get_stt_bio = fake_get_stt_bio
sys.modules["libs.stt"] = fake_stt
libs.stt = fake_stt

fake_diarize = types.ModuleType("libs.diarize")
fake_diarize.get_diarizer = fake_get_diarizer
fake_diarize.diarize_wav = fake_diarize_wav
sys.modules["libs.diarize"] = fake_diarize
libs.diarize = fake_diarize

import stt_server  # noqa: E402  (must follow the backend stubs)
from libs import config, model_pool  # noqa: E402  (must follow the backend stubs)


@pytest.fixture
def client(monkeypatch):
    """Flask test client backed by a one-slot model pool holding a sentinel model."""
    pool: queue.Queue = queue.Queue()
    pool.put("model-sentinel")
    monkeypatch.setattr(model_pool, "MODEL_POOL", pool)
    monkeypatch.setattr(config, "MODEL_POOL_SIZE", 1)
    # Pinned rather than inherited: a machine with DIARIZE_ENABLED set in its environment would
    # otherwise turn the disabled-build test into a real pool wait.
    monkeypatch.setattr(config, "DIARIZE_ENABLED", False)
    return stt_server.app.test_client()


@pytest.fixture
def stt_module():
    """The stubbed libs.stt module, so a test can swap get_stt_bio for its own."""
    return fake_stt


@pytest.fixture
def diarize_module():
    """The stubbed libs.diarize module, so a test can swap diarize_wav for its own."""
    return fake_diarize


@pytest.fixture
def diarize_client(client, monkeypatch):
    """Test client with diarization switched on and a one-slot diarizer pool."""
    pool: queue.Queue = queue.Queue()
    pool.put("diarizer-sentinel")
    monkeypatch.setattr(model_pool, "DIARIZER_POOL", pool)
    monkeypatch.setattr(config, "DIARIZE_ENABLED", True)
    monkeypatch.setattr(config, "DIARIZE_POOL_SIZE", 1)
    return client
