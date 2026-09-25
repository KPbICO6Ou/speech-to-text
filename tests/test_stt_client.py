#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stt_client.py: the --model and --language options and the form fields it sends."""

import stt_client


def test_model_and_language_in_both_spellings():
    """`--flag VALUE` and `--flag=VALUE` both work, and the files keep their order."""
    args = stt_client.build_parser().parse_args(["--model", "turbo", "--language=ru", "a.wav", "b.mp3"])
    assert (args.model, args.language, args.files, args.list) == ("turbo", "ru", ["a.wav", "b.mp3"], False)


def test_options_default_to_none():
    """Without the flags nothing is chosen, so the server's own defaults apply."""
    args = stt_client.build_parser().parse_args(["a.wav"])
    assert (args.model, args.language) == (None, None)


def test_list_needs_no_files():
    """`--list` alone asks for the catalogue."""
    assert stt_client.build_parser().parse_args(["--list"]).list is True


def test_empty_options_are_not_sent():
    """Only what the user gave goes into the form, so the server default applies otherwise."""
    assert stt_client.build_form_fields(None, "") == {}
