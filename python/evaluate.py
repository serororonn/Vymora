#!/usr/bin/env python3
"""Compare an estimated MIDI with a ground-truth MIDI."""
import argparse
import json
from pathlib import Path

import numpy as np
import pretty_midi


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
                }
            )
    return sorted(notes, key=lambda note: (note["start"], note["pitch"], note["end"]))


def compare_midis(estimated_path, reference_path, onset_tolerance=0.08, pitch_tolerance=0):
    estimated = _notes(estimated_path)
    reference = _notes(reference_path)
    unmatched_estimated = set(range(len(estimated)))
    matches = []

    for reference_index, reference_note in enumerate(reference):
        candidates = [
            index
            for index in unmatched_estimated
            if abs(estimated[index]["start"] - reference_note["start"]) <= onset_tolerance
            and abs(estimated[index]["pitch"] - reference_note["pitch"]) <= pitch_tolerance
        ]
        if not candidates:
            continue
        estimated_index = min(
            candidates,
            key=lambda index: abs(estimated[index]["start"] - reference_note["start"]),
        )
        unmatched_estimated.remove(estimated_index)
        matches.append((estimated[estimated_index], reference_note))

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
    return {
        "estimated_notes": len(estimated),
        "reference_notes": len(reference),
        "matched_notes": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "mean_onset_error_seconds": round(float(np.mean(onset_errors)) if onset_errors else 0.0, 5),
        "mean_duration_error_seconds": round(float(np.mean(duration_errors)) if duration_errors else 0.0, 5),
        "mean_velocity_error": round(float(np.mean(velocity_errors)) if velocity_errors else 0.0, 3),
    }


def main():
    parser = argparse.ArgumentParser(description="Compare estimated MIDI with reference MIDI")
    parser.add_argument("estimated", type=Path)
    parser.add_argument("reference", type=Path)
    parser.add_argument("--onset-tolerance", type=float, default=0.08)
    args = parser.parse_args()
    print(json.dumps(compare_midis(args.estimated, args.reference, args.onset_tolerance), indent=2))


if __name__ == "__main__":
    main()
