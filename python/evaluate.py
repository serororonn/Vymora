#!/usr/bin/env python3
"""Compare an estimated MIDI with a ground-truth MIDI."""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pretty_midi


TRACK_ALIASES = {
    "vocal": "vocals",
    "voice": "vocals",
    "vocals": "vocals",
    "drum": "drums",
    "drums": "drums",
    "kick": "kick",
    "snare": "snare",
    "hi-hat": "hi-hat",
    "hihat": "hi-hat",
    "hi hat": "hi-hat",
}


def _track_key(name):
    normalized = " ".join(str(name).lower().replace("_", " ").split())
    return TRACK_ALIASES.get(normalized, normalized)


def _notes(path):
    midi = pretty_midi.PrettyMIDI(str(path))
    notes = []
    for instrument in midi.instruments:
        for note in instrument.notes:
            notes.append(
                {
                    "pitch": note.pitch,
                    "start": note.start,
                    "end": note.end,
                    "velocity": note.velocity,
                    "track": instrument.name or str(instrument.program),
                    "track_key": _track_key(instrument.name or str(instrument.program)),
                }
            )
    return sorted(notes, key=lambda note: (note["start"], note["pitch"], note["end"]))


def _match_notes(estimated, reference, onset_tolerance, pitch_tolerance):
    """Match notes by track, pitch, and onset using the lowest-cost pairs first."""
    candidates = []
    for estimated_index, estimated_note in enumerate(estimated):
        for reference_index, reference_note in enumerate(reference):
            if estimated_note["track_key"] != reference_note["track_key"]:
                continue
            if estimated_note["pitch"] != reference_note["pitch"] and abs(estimated_note["pitch"] - reference_note["pitch"]) > pitch_tolerance:
                continue
            onset_error = abs(estimated_note["start"] - reference_note["start"])
            if onset_error <= onset_tolerance:
                duration_error = abs(
                    (estimated_note["end"] - estimated_note["start"])
                    - (reference_note["end"] - reference_note["start"])
                )
                candidates.append((onset_error, duration_error, estimated_index, reference_index))

    matches = []
    used_estimated = set()
    used_reference = set()
    for _, _, estimated_index, reference_index in sorted(candidates):
        if estimated_index in used_estimated or reference_index in used_reference:
            continue
        used_estimated.add(estimated_index)
        used_reference.add(reference_index)
        matches.append((estimated[estimated_index], reference[reference_index]))
    return matches


def _metrics(estimated, reference, matches, offset_tolerance):
    true_positives = len(matches)
    false_positives = len(estimated) - true_positives
    false_negatives = len(reference) - true_positives
    precision = true_positives / len(estimated) if estimated else 0.0
    recall = true_positives / len(reference) if reference else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    onset_errors = [abs(estimated_note["start"] - reference_note["start"]) for estimated_note, reference_note in matches]
    duration_errors = [
        abs((estimated_note["end"] - estimated_note["start"]) - (reference_note["end"] - reference_note["start"]))
        for estimated_note, reference_note in matches
    ]
    velocity_errors = [
        abs(estimated_note["velocity"] - reference_note["velocity"])
        for estimated_note, reference_note in matches
    ]
    offset_matches = [
        (estimated_note, reference_note)
        for estimated_note, reference_note in matches
        if abs(estimated_note["end"] - reference_note["end"]) <= offset_tolerance
    ]
    offset_true_positives = len(offset_matches)
    offset_precision = offset_true_positives / len(estimated) if estimated else 0.0
    offset_recall = offset_true_positives / len(reference) if reference else 0.0
    offset_f1 = (
        2 * offset_precision * offset_recall / (offset_precision + offset_recall)
        if offset_precision + offset_recall
        else 0.0
    )
    return {
        "estimated_notes": len(estimated),
        "reference_notes": len(reference),
        "matched_notes": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "offset_matched_notes": offset_true_positives,
        "offset_precision": round(offset_precision, 4),
        "offset_recall": round(offset_recall, 4),
        "offset_f1": round(offset_f1, 4),
        "mean_onset_error_seconds": round(float(np.mean(onset_errors)) if onset_errors else 0.0, 5),
        "mean_duration_error_seconds": round(float(np.mean(duration_errors)) if duration_errors else 0.0, 5),
        "mean_velocity_error": round(float(np.mean(velocity_errors)) if velocity_errors else 0.0, 3),
    }


def compare_midis(estimated_path, reference_path, onset_tolerance=0.08, pitch_tolerance=0, offset_tolerance=0.1):
    estimated = _notes(estimated_path)
    reference = _notes(reference_path)
    matches = _match_notes(estimated, reference, onset_tolerance, pitch_tolerance)
    result = _metrics(estimated, reference, matches, offset_tolerance)

    estimated_by_track = defaultdict(list)
    reference_by_track = defaultdict(list)
    for note in estimated:
        estimated_by_track[note["track_key"]].append(note)
    for note in reference:
        reference_by_track[note["track_key"]].append(note)

    track_metrics = {}
    for track in sorted(set(estimated_by_track) | set(reference_by_track)):
        track_estimated = estimated_by_track[track]
        track_reference = reference_by_track[track]
        track_matches = _match_notes(track_estimated, track_reference, onset_tolerance, pitch_tolerance)
        track_metrics[track] = _metrics(track_estimated, track_reference, track_matches, offset_tolerance)
    result["tracks"] = track_metrics
    result["matching"] = {
        "track_aware": True,
        "onset_tolerance_seconds": onset_tolerance,
        "offset_tolerance_seconds": offset_tolerance,
        "pitch_tolerance_semitones": pitch_tolerance,
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Compare estimated MIDI with reference MIDI")
    parser.add_argument("estimated", type=Path)
    parser.add_argument("reference", type=Path)
    parser.add_argument("--onset-tolerance", type=float, default=0.08)
    parser.add_argument("--offset-tolerance", type=float, default=0.1)
    parser.add_argument("--pitch-tolerance", type=int, default=0)
    args = parser.parse_args()
    print(
        json.dumps(
            compare_midis(
                args.estimated,
                args.reference,
                onset_tolerance=args.onset_tolerance,
                pitch_tolerance=args.pitch_tolerance,
                offset_tolerance=args.offset_tolerance,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
