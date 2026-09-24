#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The REAL libs/parakeet.py, which every other test replaces with a stub."""

import importlib.util
import os

MODULE_PATH = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)), "libs", "parakeet.py")


def load_real_parakeet():
    """Load libs/parakeet.py from its file, bypassing the stub in sys.modules.

    Not registered in sys.modules: the stub is what the rest of the suite needs, and replacing
    it here would leak into whatever runs next.
    """
    spec = importlib.util.spec_from_file_location("libs_parakeet_real", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def token(text, start, end):
    """Build one token timestamp as the processor emits it, in seconds."""
    return {"token": text, "start": start, "end": end}


def test_module_imports_and_exposes_the_same_surface_as_whisper():
    """Interchangeability is the whole design, so the names and their absence both matter."""
    module = load_real_parakeet()
    for name in ("get_model", "get_stt_bio", "get_stt_segments", "describe_backend", "group_tokens"):
        assert callable(getattr(module, name)), name
    # It detects the language itself, so it deliberately has no language table to resolve against.
    assert not hasattr(module, "normalize_language_code")


def test_tokens_join_without_inserted_spaces():
    """Tokens are subwords; joining them with a separator would break every word."""
    module = load_real_parakeet()
    segments = module.group_tokens([token(" Hel", 0.0, 0.2), token("lo", 0.2, 0.4)])
    assert len(segments) == 1
    assert segments[0]["text"] == " Hello"


def test_a_silence_starts_a_new_segment():
    """A gap longer than the threshold is a phrase boundary, which is what align.py joins on."""
    module = load_real_parakeet()
    segments = module.group_tokens(
        [token(" one", 0.0, 0.3), token(" two", 5.0, 5.4)],
    )
    assert [s["text"] for s in segments] == [" one", " two"]
    assert segments[1]["start"] == 5.0


def test_no_tokens_is_no_segments():
    """Silence transcribes to nothing rather than to an empty phrase."""
    assert load_real_parakeet().group_tokens([]) == []


def test_describe_backend_reports_a_language_blind_backend():
    """The catalogue must say this backend takes no language, or ?language= becomes a lie."""
    row = load_real_parakeet().describe_backend()
    assert row["backend"] == "parakeet"
    assert row["accepts_language"] is False
    assert row["default_language"] is None
    assert len(row["languages"]) == 25
    assert "ru" in row["languages"] and "uk" in row["languages"]


def test_languages_are_refused_for_an_unknown_model_id(monkeypatch):
    """The 25 codes are carried for one id; another gets null rather than that list."""
    module = load_real_parakeet()
    monkeypatch.setattr(module.config, "PARAKEET_MODEL", "nvidia/parakeet-something-else")
    row = module.describe_backend()
    assert row["languages"] is None
    assert row["languages_source"] is None
