#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""POST /api/stt — per-request ``language`` option."""

import io
import re

from tests.conftest import make_wav

REQ_ID_RE = re.compile(r"^[0-9a-f]{12}$")


def _capture(stt_module, monkeypatch):
    seen = {}

    def cap(bio, model=None, device=None, language=None):
        seen["language"] = language
        return "stub transcription"

    monkeypatch.setattr(stt_module, "get_stt_bio", cap)
    return seen


def test_language_query_passed(client, stt_module, monkeypatch):
    seen = _capture(stt_module, monkeypatch)
    resp = client.post("/api/stt?language=ru", data=make_wav(), content_type="audio/wav")
    assert resp.status_code == 200
    assert seen["language"] == "ru"


def test_language_form_field_passed(client, stt_module, monkeypatch):
    seen = _capture(stt_module, monkeypatch)
    resp = client.post(
        "/api/stt",
        data={"file": (io.BytesIO(make_wav()), "sample.wav"), "language": "ru"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert seen["language"] == "ru"


def test_language_default_none(client, stt_module, monkeypatch):
    seen = _capture(stt_module, monkeypatch)
    resp = client.post("/api/stt", data=make_wav(), content_type="audio/wav")
    assert resp.status_code == 200
    assert seen["language"] is None  # server WHISPER_LANGUAGE default is used


def test_language_auto_passed(client, stt_module, monkeypatch):
    seen = _capture(stt_module, monkeypatch)
    resp = client.post("/api/stt?language=AUTO", data=make_wav(), content_type="audio/wav")
    assert resp.status_code == 200
    assert seen["language"] == "auto"  # normalized lower-case; autodetect resolved in stt.py


def test_language_empty_is_none(client, stt_module, monkeypatch):
    seen = _capture(stt_module, monkeypatch)
    resp = client.post("/api/stt?language=", data=make_wav(), content_type="audio/wav")
    assert resp.status_code == 200
    assert seen["language"] is None


def test_invalid_language_400(client):
    resp = client.post("/api/stt?language=russian", data=make_wav(), content_type="audio/wav")
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error"] == "Invalid language"
    assert set(body.keys()) == {"error", "request_id"}
    assert REQ_ID_RE.match(body["request_id"])
