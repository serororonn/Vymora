"""Faithful MIDI analysis and conservative post-processing."""
import json
import argparse
from pathlib import Path

import numpy as np
import pretty_midi
from mido import MidiFile, MetaMessage, bpm2tempo, second2tick


BASS_RANGE = (28, 72)
DRUM_NAMES = {"kick": 36, "snare": 38, "hi-hat": 42}
PITCH_CLASS_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def _tempo_and_bar_length(midi):
    tempos = midi.get_tempo_changes()[1]
    tempo = float(tempos[0]) if len(tempos) else 120.0
    return tempo, 60.0 / tempo * 4.0


def _chord_name(notes):
    if not notes:
        return "N.C."
    histogram = np.bincount([note.pitch % 12 for note in notes], minlength=12)
    root = int(np.argmax(histogram))
    major = histogram[(root + 4) % 12]
    minor = histogram[(root + 3) % 12]
    suffix = "m" if minor > major else ""
    return f"{PITCH_CLASS_NAMES[root]}{suffix}"


def analyze_midi(path, bars_per_section=4):
    """Return faithful structural information without changing the MIDI."""
    midi = pretty_midi.PrettyMIDI(str(path))
    tempo, bar_length = _tempo_and_bar_length(midi)
    end_time = midi.get_end_time()
    section_length = bar_length * bars_per_section
    sections = []
    start = 0.0
    all_notes = [note for instrument in midi.instruments for note in instrument.notes]
    while start < end_time:
        end = min(start + section_length, end_time)
        notes = [note for note in all_notes if start <= note.start < end]
        density = len(notes) / max(end - start, 1e-9)
        sections.append({"start": round(start, 4), "end": round(end, 4), "density": round(density, 4), "chord": _chord_name(notes)})
        start = end
    if sections:
        median_density = float(np.median([section["density"] for section in sections]))
        for section in sections:
            section["level"] = "high" if section["density"] >= median_density else "low"
    return {"tempo": round(tempo, 3), "bar_length": round(bar_length, 4), "sections": sections}


def _correct_bass(instrument):
    """Keep bass notes, only correcting obvious octave and overlap errors."""
    notes = sorted(instrument.notes, key=lambda note: (note.start, note.pitch, note.end))
    corrected = []
    for note in notes:
        pitch = note.pitch
        while pitch < BASS_RANGE[0]:
            pitch += 12
        while pitch > BASS_RANGE[1]:
            pitch -= 12
        if corrected and pitch == corrected[-1].pitch and note.start < corrected[-1].end:
            corrected[-1].end = max(corrected[-1].end, note.end)
            corrected[-1].velocity = max(corrected[-1].velocity, note.velocity)
            continue
        corrected.append(pretty_midi.Note(note.velocity, pitch, note.start, note.end))
    instrument.notes = corrected


def _complete_repeated_drum_holes(instrument, bar_length):
    """Fill only an obvious one-hit hole in a repeated drum interval."""
    notes_by_pitch = {}
    for note in instrument.notes:
        notes_by_pitch.setdefault(note.pitch, []).append(note)
    additions = []
    for pitch, notes in notes_by_pitch.items():
        notes = sorted(notes, key=lambda note: note.start)
        if len(notes) < 3:
            continue
        intervals = np.diff([note.start for note in notes])
        interval = float(np.min(intervals))
        if interval <= 0 or interval > bar_length / 2:
            continue
        for previous, current in zip(notes, notes[1:]):
            gap = current.start - previous.start
            if 1.75 * interval <= gap <= 2.25 * interval:
                start = previous.start + interval
                additions.append(pretty_midi.Note(previous.velocity, pitch, start, start + min(previous.end - previous.start, 0.08)))
    instrument.notes.extend(additions)
    instrument.notes.sort(key=lambda note: (note.start, note.pitch))


def _add_analysis_markers(path, analysis):
    midi = MidiFile(str(path))
    marker_track = next((track for track in midi.tracks if track.name == "Structure Analysis"), None)
    if marker_track is None:
        marker_track = midi.add_track(name="Structure Analysis")
    else:
        marker_track.clear()
    ticks_per_beat = midi.ticks_per_beat
    tempo = bpm2tempo(analysis["tempo"])
    previous_tick = 0
    for index, section in enumerate(analysis["sections"], start=1):
        absolute_tick = int(second2tick(section["start"], ticks_per_beat, tempo))
        marker_track.append(
            MetaMessage(
                "marker",
                text=f"Section {index:02d} | {section['level']} | {section['chord']}",
                time=max(0, absolute_tick - previous_tick),
            )
        )
        previous_tick = absolute_tick
    midi.save(str(path))


def polish_midi(input_path, output_path=None, faithful=True):
    """Analyze and conservatively polish a generated MIDI.

    No new melodic or harmonic notes are generated. Drum additions are limited
    to a single missing hit between two regular, repeated hits.
    """
    input_path = Path(input_path)
    output_path = Path(output_path or input_path)
    midi = pretty_midi.PrettyMIDI(str(input_path))
    analysis = analyze_midi(input_path)
    for instrument in midi.instruments:
        name = instrument.name.lower()
        if not instrument.is_drum and ("bass" in name or instrument.program == 33):
            _correct_bass(instrument)
        if instrument.is_drum:
            _complete_repeated_drum_holes(instrument, analysis["bar_length"])
    midi.write(str(output_path))
    _add_analysis_markers(output_path, analysis)
    return analysis


def write_analysis(path, analysis):
    Path(path).write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Analyze and conservatively polish a MIDI")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--analysis", type=Path, help="解析結果をJSONでも保存")
    args = parser.parse_args()
    analysis = polish_midi(args.input, args.output)
    if args.analysis:
        write_analysis(args.analysis, analysis)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
