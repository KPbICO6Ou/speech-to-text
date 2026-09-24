#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""POST /api/stt - per-request ``language`` option."""

import io
import re

from tests.helpers import make_wav

REQ_ID_RE = re.compile(r"^[0-9a-f]{12}$")


def capture_language(stt_module, monkeypatch) -> dict:
    """Swap get_stt_bio for a stub that records the language it was called with."""
    seen = {}

    def record_language(bio, model=None, device=None, language=None):
        """Stand in for stt.get_stt_bio() and remember the language argument."""
        seen["language"] = language
        return "stub transcription"

    monkeypatch.setattr(stt_module, "get_stt_bio", record_language)
    return seen


def test_language_query_passed(client, stt_module, monkeypatch):
    """?language=ru reaches the backend unchanged."""
    seen = capture_language(stt_module, monkeypatch)
    resp = client.post("/api/stt?language=ru", data=make_wav(), content_type="audio/wav")
    assert resp.status_code == 200
    assert seen["language"] == "ru"


def test_language_form_field_passed(client, stt_module, monkeypatch):
    """A multipart ``language`` field works the same as the query string."""
    seen = capture_language(stt_module, monkeypatch)
    resp = client.post(
        "/api/stt",
        data={"file": (io.BytesIO(make_wav()), "sample.wav"), "language": "ru"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert seen["language"] == "ru"


def test_language_default_none(client, stt_module, monkeypatch):
    """Without the option the backend receives None and applies WHISPER_LANGUAGE."""
    seen = capture_language(stt_module, monkeypatch)
    resp = client.post("/api/stt", data=make_wav(), content_type="audio/wav")
    assert resp.status_code == 200
    assert seen["language"] is None


def test_language_auto_passed(client, stt_module, monkeypatch):
    """``auto`` is lower-cased and forwarded; autodetect is resolved in libs/stt.py."""
    seen = capture_language(stt_module, monkeypatch)
    resp = client.post("/api/stt?language=AUTO", data=make_wav(), content_type="audio/wav")
    assert resp.status_code == 200
    assert seen["language"] == "auto"


def test_language_empty_is_none(client, stt_module, monkeypatch):
    """An empty value is treated as "not given"."""
    seen = capture_language(stt_module, monkeypatch)
    resp = client.post("/api/stt?language=", data=make_wav(), content_type="audio/wav")
    assert resp.status_code == 200
    assert seen["language"] is None


def test_unknown_language_400(client):
    """A language the backend does not know is refused here, rather than raising there.

    `zz` has the shape of a code and is not one. The old shape check let it through, Whisper
    raised on it, and the broad handler turned that into a 500.
    """
    resp = client.post("/api/stt?language=zz", data=make_wav(), content_type="audio/wav")
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error"] == "Invalid language"
    assert set(body.keys()) == {"error", "request_id"}
    assert REQ_ID_RE.match(body["request_id"])


def test_language_name_is_resolved_to_its_code(client, stt_module, monkeypatch):
    """A full English name is what Whisper itself accepts, so the server accepts it too.

    The previous behaviour refused `russian` with a 400 although the backend understood it.
    """
    seen = capture_language(stt_module, monkeypatch)
    resp = client.post("/api/stt?language=russian", data=make_wav(), content_type="audio/wav")
    assert resp.status_code == 200
    assert seen["language"] == "ru"


def test_language_name_is_case_insensitive(client, stt_module, monkeypatch):
    """Casing is the caller's business, not the server's."""
    seen = capture_language(stt_module, monkeypatch)
    resp = client.post("/api/stt?language=RUSSIAN", data=make_wav(), content_type="audio/wav")
    assert resp.status_code == 200
    assert seen["language"] == "ru"


def test_a_typo_is_still_refused(client):
    """Resolution must not be so generous that a misspelling silently transcribes as something else."""
    resp = client.post("/api/stt?language=russsian", data=make_wav(), content_type="audio/wav")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Invalid language"
