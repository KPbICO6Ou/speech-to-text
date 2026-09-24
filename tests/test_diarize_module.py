#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import the REAL libs/diarize.py, which every other test replaces with a stub."""

import importlib.util
import io
import os
import wave

import pytest

MODULE_PATH = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)), "libs", "diarize.py")


def load_real_diarize():
    """Load libs/diarize.py from its file, bypassing the stub sitting in sys.modules.

    Deliberately not registered in sys.modules: the stub is what the rest of the suite needs,
    and replacing it here would leak into whatever runs next.
    """
    spec = importlib.util.spec_from_file_location("libs_diarize_real", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_wav_bytes(sample_rate: int, n_frames: int = 160) -> bytes:
    """Build a silent 16-bit mono WAV at the given rate."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(b"\x00\x00" * n_frames)
    return buf.getvalue()


def test_module_imports_and_exposes_its_surface():
    """The module imports for real, so a broken module-level import fails here rather than in production."""
    module = load_real_diarize()
    for name in ("get_diarizer", "diarize_wav", "read_mono_16k", "resolve_device", "main"):
        assert callable(getattr(module, name)), name


def test_read_mono_16k_accepts_the_servers_format():
    """The buffer libs/audio.py produces decodes to a mono float32 waveform."""
    module = load_real_diarize()
    data = module.read_mono_16k(io.BytesIO(make_wav_bytes(16000)))
    assert data.ndim == 1
    assert str(data.dtype) == "float32"
    assert len(data) == 160


def test_read_mono_16k_refuses_another_rate():
    """A wrong rate is refused rather than resampled, so a caller that skipped the conversion is visible."""
    module = load_real_diarize()
    with pytest.raises(ValueError, match="16000 Hz"):
        module.read_mono_16k(io.BytesIO(make_wav_bytes(44100)))
