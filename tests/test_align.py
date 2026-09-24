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
    # The interruption sits inside the second phrase, not in the gap before it, so the two
    # phrases still merge; an interruption in the gap would correctly keep them apart.
    result = align.attribute_segments(
        [segment(0.0, 1.0), segment(1.1, 2.0)],
        [turn(0, 0.0, 2.5), turn(1, 1.5, 1.8)],
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


def test_a_run_does_not_merge_across_another_speakers_turn():
    """Speaker 1 talked between two phrases of speaker 0 without producing any words.

    Found on the deployment host: the transcriber dropped every word of one voice, the two
    remaining phrases of the other merged, and the result claimed one person spoke straight
    through the other's turn.
    """
    result = align.attribute_segments(
        [segment(0.1, 6.5, " first"), segment(12.7, 18.9, " second")],
        [turn(0, 0.0, 6.5), turn(1, 6.9, 11.6), turn(0, 12.4, 18.9)],
    )
    assert [(r["speaker"], r["start"], r["end"]) for r in result] == [(0, 0.1, 6.5), (0, 12.7, 18.9)]


def test_a_run_still_merges_when_nobody_else_spoke_in_the_gap():
    """The fix must not stop ordinary merging of one speaker's consecutive phrases."""
    result = align.attribute_segments(
        [segment(0.0, 1.0, " one"), segment(1.5, 2.0, " two")],
        [turn(0, 0.0, 2.5), turn(1, 5.0, 6.0)],
    )
    assert len(result) == 1
    assert result[0]["text"] == "one two"


def test_word_level_input_follows_a_quick_handover():
    """Words, not phrases: a handover shorter than any pause threshold is still followed."""
    words = [segment(0.0, 0.3, " so"), segment(0.3, 0.6, " where"), segment(0.7, 1.0, " green"), segment(1.0, 1.3, " now")]
    turns = [turn(0, 0.0, 0.65), turn(1, 0.65, 1.4)]
    result = align.attribute_segments(words, turns)
    assert [(r["speaker"], r["text"]) for r in result] == [(0, "so where"), (1, "green now")]


def test_a_segment_with_no_text_is_dropped():
    """A whitespace-only segment is not speech; it must not surface as an empty run."""
    result = align.attribute_segments(
        [segment(0.0, 1.0, " hello"), segment(1.0, 1.1, "  "), segment(1.1, 2.0, " there")],
        [turn(0, 0.0, 2.5)],
    )
    assert [r["text"] for r in result] == ["hello there"]
