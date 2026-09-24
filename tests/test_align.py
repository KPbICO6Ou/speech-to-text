#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The word-to-speaker join, as pure functions: no models, no torch, no HTTP."""

from libs import align


def turn(speaker, start, end):
    """Build a diarizer turn."""
    return {"speaker": speaker, "start": start, "end": end}


def segment(start, end, text=" phrase"):
    """Build a transcription segment."""
    return {"start": start, "end": end, "text": text}


def test_alternating_speakers_keep_their_own_segments():
    """The simple case: two phrases, two turns, one each."""
    result = align.attribute_segments(
        [segment(0.0, 1.0, " hello"), segment(2.0, 3.0, " goodbye")],
        [turn(0, 0.0, 1.5), turn(1, 1.5, 3.5)],
    )
    assert [(r["speaker"], r["text"]) for r in result] == [(0, "hello"), (1, "goodbye")]


def test_a_segment_straddling_a_handover_goes_to_the_larger_share():
    """0.8-1.8 against a handover at 1.4 leaves 0.6 s with speaker 0 and 0.4 s with speaker 1."""
    result = align.attribute_segments([segment(0.8, 1.8)], [turn(0, 0.0, 1.4), turn(1, 1.4, 3.0)])
    assert result[0]["speaker"] == 0


def test_simultaneous_speech_is_marked_rather_than_hidden():
    """A segment inside an overlap goes to the longer share and says that it was contested."""
    result = align.attribute_segments([segment(1.0, 2.0)], [turn(0, 0.0, 1.6), turn(1, 0.9, 3.0)])
    assert result[0]["speaker"] == 1
    assert result[0]["overlap"] is True


def test_a_clean_segment_is_not_marked_as_overlapping():
    """Nothing is flagged when only one person was talking."""
    result = align.attribute_segments([segment(0.1, 1.0)], [turn(0, 0.0, 1.5)])
    assert result[0]["overlap"] is False


def test_a_segment_no_turn_covers_is_left_unattributed():
    """Silence from the diarizer means "not attributed", never the nearest speaker."""
    result = align.attribute_segments([segment(5.0, 6.0)], [turn(0, 0.0, 1.0)])
    assert result[0]["speaker"] is None


def test_no_turns_at_all_leaves_everything_unattributed():
    """A recording the diarizer found nobody in still returns its text."""
    result = align.attribute_segments([segment(0.0, 1.0, " hello")], [])
    assert result == [{"speaker": None, "start": 0.0, "end": 1.0, "text": "hello", "overlap": False}]


def test_consecutive_segments_of_one_speaker_merge():
    """Two phrases in a row from the same person read as one turn of speech."""
    result = align.attribute_segments(
        [segment(0.0, 1.0, " first"), segment(1.1, 2.0, " second")],
        [turn(0, 0.0, 2.5)],
    )
    assert len(result) == 1
    assert result[0]["text"] == "first second"
    assert result[0]["end"] == 2.0


def test_merging_keeps_the_overlap_flag_of_any_part():
    """If any phrase of a merged run was contested, the run says so."""
    result = align.attribute_segments(
        [segment(0.0, 1.0), segment(1.1, 2.0)],
        [turn(0, 0.0, 2.5), turn(1, 1.0, 1.5)],
    )
    assert len(result) == 1
    assert result[0]["overlap"] is True


def test_count_speakers_ignores_the_unattributed():
    """The unattributed pseudo-speaker is not a person and is not counted."""
    result = align.attribute_segments(
        [segment(0.0, 1.0), segment(9.0, 9.5)],
        [turn(0, 0.0, 1.5)],
    )
    assert align.count_speakers(result) == 1
