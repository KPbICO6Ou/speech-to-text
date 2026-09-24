#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Join transcription segments to speaker turns by time. Pure functions: no models, no torch."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# A segment nobody claims keeps this speaker rather than being handed to the nearest turn.
# Saying "not attributed" is honest; guessing is not.
UNATTRIBUTED: None = None


def overlap_seconds(first_start: float, first_end: float, second_start: float, second_end: float) -> float:
    """Seconds the two ranges share, or zero when they do not touch."""
    return max(0.0, min(first_end, second_end) - max(first_start, second_start))


def assign_speaker(segment: dict[str, Any], turns: list[dict[str, Any]]) -> int | None:
    """The speaker whose turn overlaps this segment most, or None when no turn overlaps it.

    Greatest overlap rather than the containing turn: a phrase that straddles a handover
    belongs to whoever held most of it, and a phrase inside an overlap belongs to whoever was
    speaking for longer while it happened.
    """
    best: int | None = UNATTRIBUTED
    best_overlap = 0.0
    for turn in turns:
        shared = overlap_seconds(segment["start"], segment["end"], turn["start"], turn["end"])
        if shared > best_overlap:
            best, best_overlap = turn["speaker"], shared
    return best


def is_overlapped(segment: dict[str, Any], speaker: int | None, turns: list[dict[str, Any]]) -> bool:
    """Whether another speaker was also talking during this segment.

    Reported rather than hidden: the diarizer scores each speaker channel independently, so
    genuinely simultaneous speech is a fact about the recording, and a transcript that quietly
    attributes it to one person is claiming more than anybody knows.
    """
    for turn in turns:
        if turn["speaker"] == speaker:
            continue
        if overlap_seconds(segment["start"], segment["end"], turn["start"], turn["end"]) > 0:
            return True
    return False


def continues_run(previous: dict[str, Any], segment: dict[str, Any], speaker: int | None, turns: list[dict[str, Any]]) -> bool:
    """Whether a segment extends the previous run rather than starting a new one.

    The same speaker is not enough. If somebody else held a turn in the gap between the two -
    even a turn the transcriber produced no words for - merging them would claim the first
    speaker talked straight through the second one, which the diarizer says did not happen.
    """
    if previous["speaker"] != speaker:
        return False
    for turn in turns:
        if turn["speaker"] == speaker:
            continue
        if overlap_seconds(previous["end"], segment["start"], turn["start"], turn["end"]) > 0:
            return False
    return True


def attribute_segments(segments: list[dict[str, Any]], turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attribute each transcription segment to a speaker, merging consecutive runs of one.

    Runs merge only when nobody else spoke in between; see continues_run.

    `segments` are the transcriber's own phrases with their times; `turns` are the diarizer's
    output. Neither is modified. The result carries the joined text, the range it covers and
    whether somebody else was speaking across it.
    """
    attributed: list[dict[str, Any]] = []
    for segment in segments:
        speaker = assign_speaker(segment, turns)
        overlapped = is_overlapped(segment, speaker, turns)
        text = segment["text"].strip()
        if attributed and continues_run(attributed[-1], segment, speaker, turns):
            previous = attributed[-1]
            previous["end"] = round(float(segment["end"]), 2)
            previous["text"] = f"{previous['text']} {text}".strip()
            previous["overlap"] = previous["overlap"] or overlapped
            continue
        attributed.append(
            {
                "speaker": speaker,
                "start": round(float(segment["start"]), 2),
                "end": round(float(segment["end"]), 2),
                "text": text,
                "overlap": overlapped,
            }
        )
    return attributed


def count_speakers(attributed: list[dict[str, Any]]) -> int:
    """How many distinct speakers were actually attributed, not counting the unattributed."""
    return len({segment["speaker"] for segment in attributed if segment["speaker"] is not UNATTRIBUTED})


def main():
    """No-op entry point: this module is imported for its join helpers."""
    pass


if __name__ == "__main__":
    main()
