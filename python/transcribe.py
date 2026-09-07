#!/usr/bin/env python3
"""簡易 Audio2MIDI プロトタイプ（バッチ CLI）

使い方例:
  python transcribe.py input.wav output.mid

注意: 高精度化はモデルや後処理が必要です。まずは動くプロトタイプを提供します。
"""
import argparse
import numpy as np
import librosa
import pretty_midi
from arrange_midi import polish_midi

try:
    from basic_pitch.inference import predict
    from basic_pitch import ICASSP_2022_MODEL_PATH
except ImportError:
    predict = None
    ICASSP_2022_MODEL_PATH = None


INSTRUMENTS = {
    "vocals": (53, "Vocals"),
    "bass": (33, "Bass"),
    "guitar": (24, "Guitar"),
    "piano": (0, "Piano"),
    "drums": (0, "Drums"),
    "other": (48, "Other"),
}

PITCH_RANGES = {
    "vocals": (65.0, 1047.0),
    "bass": (27.5, 523.0),
    "guitar": (73.0, 1319.0),
    "piano": (27.5, 4186.0),
    "other": (27.5, 4186.0),
}

ACCURACY_PRESETS = {
    "strong": {"onset_threshold": 0.35, "frame_threshold": 0.25, "minimum_note_length": 45.0, "peak_ratio": 0.25, "global_ratio": 0.015, "max_peaks": 4, "min_duration": 0.04},
    "normal": {"onset_threshold": 0.45, "frame_threshold": 0.3, "minimum_note_length": 60.0, "peak_ratio": 0.35, "global_ratio": 0.025, "max_peaks": 3, "min_duration": 0.06},
    "weak": {"onset_threshold": 0.55, "frame_threshold": 0.4, "minimum_note_length": 90.0, "peak_ratio": 0.45, "global_ratio": 0.04, "max_peaks": 2, "min_duration": 0.09},
}


def _accuracy_values(accuracy):
    return ACCURACY_PRESETS.get(accuracy, ACCURACY_PRESETS["normal"])


def transcribe_drums(input_path, sr=16000, hop_length=256):
    y, sr = librosa.load(input_path, sr=sr, mono=True)
    onset_frames = librosa.onset.onset_detect(y=y, sr=sr, hop_length=hop_length, backtrack=False)
    onset_strength = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]
    instruments = {
        36: pretty_midi.Instrument(program=0, is_drum=True, name="Kick"),
        38: pretty_midi.Instrument(program=0, is_drum=True, name="Snare"),
        42: pretty_midi.Instrument(program=0, is_drum=True, name="Hi-Hat"),
    }

    for frame in onset_frames:
        start = float(librosa.frames_to_time(frame, sr=sr, hop_length=hop_length))
        end = min(len(y), (frame + 1) * hop_length)
        sample = y[frame * hop_length:end]
        level = float(onset_strength[frame]) if frame < len(onset_strength) else 1.0
        centroid = float(spectral_centroid[frame]) if frame < len(spectral_centroid) else 0.0
        if centroid < 180:
            pitch = 36  # bass drum
        elif centroid > 4000:
            pitch = 42  # closed hi-hat
        else:
            pitch = 38  # snare
        velocity = int(np.clip(45 + level * 10 + np.sqrt(np.mean(sample ** 2)) * 80, 1, 127))
        instruments[pitch].notes.append(
            pretty_midi.Note(velocity=velocity, pitch=pitch, start=start, end=start + 0.08)
        )
    return instruments


def transcribe_instrument(input_path, instrument_name, sr=16000, fmin=65.0, fmax=2093.0, hop_length=256, accuracy="normal"):
    if instrument_name == "drums":
        raise ValueError("drums must be expanded into individual drum tracks")
    program, track_name = INSTRUMENTS[instrument_name]
    y, sr = librosa.load(input_path, sr=sr, mono=True)

    # 基本ピッチ推定（librosa.pyin）
    f0, voiced_flag, voiced_prob = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr, hop_length=hop_length)
    values = _accuracy_values(accuracy)
    voiced = np.isfinite(f0) & (voiced_prob >= values["frame_threshold"])
    midi_values = np.full(len(f0), np.nan)
    midi_values[voiced] = librosa.hz_to_midi(f0[voiced])
    frames = np.arange(len(f0))
    times = librosa.frames_to_time(frames, sr=sr, hop_length=hop_length)

    instrument = pretty_midi.Instrument(program=program, name=track_name)

    n_frames = len(f0)
    i = 0
    # 連続した有声音部分をノートとしてまとめる簡易ロジック
    while i < n_frames:
        if not voiced[i]:
            i += 1
            continue
        start = times[i]
        freqs = []
        amps = []
        j = i
        while j < n_frames and voiced[j]:
            if j > i and abs(midi_values[j] - midi_values[j - 1]) > 2.5:
                break
            freqs.append(f0[j])
            frame_start = int(j * hop_length)
            frame_end = min(len(y), frame_start + hop_length)
            frame = y[frame_start:frame_end]
            amp = np.sqrt(np.mean(frame ** 2)) if len(frame) > 0 else 0.0
            amps.append(amp)
            j += 1
        end = times[j - 1] + (hop_length / sr)
        if end - start < values["min_duration"]:
            i = j
            continue
        median_freq = float(np.median(freqs))
        pitch = int(np.clip(np.round(librosa.hz_to_midi(median_freq)), 0, 127))
        # 簡易ベロシティ: セグメントの振幅に基づくスケーリング
        max_amp = max(amps) if amps else 1e-6
        mean_amp = float(np.mean(amps)) if amps else 0.0
        velocity = int(np.clip((mean_amp / (max_amp + 1e-9)) * 120 + 7, 1, 127))
        note = pretty_midi.Note(velocity=velocity, pitch=pitch, start=start, end=end)
        instrument.notes.append(note)
        i = j

    return instrument


def transcribe_polyphonic(input_path, instrument_name, fmin=None, fmax=None, accuracy="normal"):
    """Extract overlapping notes from one separated stem with Basic Pitch."""
    if predict is None:
        raise RuntimeError("Basic Pitchがインストールされていません")
    range_min, range_max = PITCH_RANGES.get(instrument_name, (27.5, 4186.0))
    minimum_frequency = max(fmin or range_min, range_min)
    maximum_frequency = min(fmax or range_max, range_max)
    values = _accuracy_values(accuracy)
    _, midi_data, _ = predict(
        str(input_path),
        model_or_model_path=ICASSP_2022_MODEL_PATH,
        onset_threshold=values["onset_threshold"],
        frame_threshold=values["frame_threshold"],
        minimum_note_length=values["minimum_note_length"],
        minimum_frequency=minimum_frequency,
        maximum_frequency=maximum_frequency,
    )
    source_instrument = next((item for item in midi_data.instruments if not item.is_drum), None)
    program, track_name = INSTRUMENTS[instrument_name]
    instrument = pretty_midi.Instrument(program=program, name=track_name)
    if source_instrument is not None:
        instrument.notes.extend(source_instrument.notes)
    return instrument


def transcribe_polyphonic_fallback(input_path, instrument_name, sr=16000, fmin=65.0, fmax=2093.0, hop_length=256, accuracy="normal"):
    """Estimate several simultaneous notes per frame when Basic Pitch is unavailable."""
    range_min, range_max = PITCH_RANGES.get(instrument_name, (27.5, 4186.0))
    fmin = max(fmin, range_min)
    fmax = min(fmax, range_max)
    y, sr = librosa.load(input_path, sr=sr, mono=True)
    pitches, magnitudes = librosa.piptrack(y=y, sr=sr, hop_length=hop_length, fmin=fmin, fmax=fmax)
    times = librosa.frames_to_time(np.arange(pitches.shape[1]), sr=sr, hop_length=hop_length)
    program, track_name = INSTRUMENTS[instrument_name]
    instrument = pretty_midi.Instrument(program=program, name=track_name)
    active = {}
    max_magnitude = float(np.max(magnitudes)) if magnitudes.size else 1.0
    values = _accuracy_values(accuracy)

    for frame_index in range(pitches.shape[1]):
        column = magnitudes[:, frame_index]
        threshold = max(float(np.max(column)) * values["peak_ratio"], max_magnitude * values["global_ratio"])
        candidates = np.flatnonzero(column >= threshold)
        candidates = candidates[np.argsort(column[candidates])[-values["max_peaks"]:]] if len(candidates) else []
        current = set()
        for bin_index in candidates:
            frequency = float(pitches[bin_index, frame_index])
            if frequency <= 0:
                continue
            pitch = int(np.clip(np.round(librosa.hz_to_midi(frequency)), 0, 127))
            current.add(pitch)
            if pitch not in active:
                active[pitch] = [times[frame_index], frame_index, float(column[bin_index])]
            else:
                active[pitch][1] = frame_index
                active[pitch][2] = max(active[pitch][2], float(column[bin_index]))
        for pitch in list(active):
            if pitch not in current:
                start, last_frame, magnitude = active.pop(pitch)
                end = times[last_frame] + hop_length / sr
                if end - start >= values["min_duration"]:
                    velocity = int(np.clip(40 + magnitude / max_magnitude * 87, 1, 127))
                    instrument.notes.append(pretty_midi.Note(velocity=velocity, pitch=pitch, start=start, end=end))
    for pitch, (start, last_frame, magnitude) in active.items():
        end = times[last_frame] + hop_length / sr
        if end - start >= values["min_duration"]:
            velocity = int(np.clip(40 + magnitude / max_magnitude * 87, 1, 127))
            instrument.notes.append(pretty_midi.Note(velocity=velocity, pitch=pitch, start=start, end=end))
    return instrument


def _resolve_tempo(input_path, tempo, sr):
    if tempo > 0:
        return tempo
    y, loaded_sr = librosa.load(input_path, sr=sr, mono=True)
    estimated_tempo, _ = librosa.beat.beat_track(y=y, sr=loaded_sr, hop_length=256)
    estimated_tempo = float(np.asarray(estimated_tempo).reshape(-1)[0])
    return estimated_tempo if estimated_tempo > 0 else 120.0


def transcribe(input_path, output_path, sr=16000, fmin=65.0, fmax=2093.0, hop_length=256, tempo=0.0, accuracy="normal"):
    tempo = _resolve_tempo(input_path, tempo, sr)
    pm = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    pm.instruments.append(
        transcribe_instrument(input_path, "piano", sr=sr, fmin=fmin, fmax=fmax, hop_length=hop_length, accuracy=accuracy)
    )
    pm.write(output_path)
    polish_midi(output_path, output_path)


def transcribe_stems(stem_paths, output_path, sr=16000, fmin=65.0, fmax=2093.0, hop_length=256, progress=None, high_accuracy=True, tempo=0.0, accuracy="normal"):
    if tempo <= 0:
        tempo = 120.0
    pm = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    instrument_items = [(name, path) for name, path in stem_paths.items() if name in INSTRUMENTS]
    track_count = len(instrument_items) + (2 if "drums" in stem_paths else 0)
    completed_tracks = 0
    for instrument_name, stem_path in instrument_items:
        if instrument_name not in INSTRUMENTS:
            continue
        if instrument_name == "drums":
            drum_tracks = transcribe_drums(stem_path, sr=sr, hop_length=hop_length)
            pm.instruments.extend(drum_tracks.values())
            completed_tracks += len(drum_tracks)
        else:
            if high_accuracy and predict is not None:
                track = transcribe_polyphonic(stem_path, instrument_name, fmin=fmin, fmax=fmax, accuracy=accuracy)
            elif high_accuracy:
                track = transcribe_polyphonic_fallback(
                    stem_path, instrument_name, sr=sr, fmin=fmin, fmax=fmax, hop_length=hop_length, accuracy=accuracy
                )
            else:
                track = transcribe_instrument(stem_path, instrument_name, sr=sr, fmin=fmin, fmax=fmax, hop_length=hop_length, accuracy=accuracy)
            pm.instruments.append(track)
            completed_tracks += 1
        if progress is not None:
            progress(completed_tracks / track_count)
    pm.write(output_path)
    polish_midi(output_path, output_path)


def main():
    parser = argparse.ArgumentParser(description="Simple Audio2MIDI prototype")
    parser.add_argument("input", help="input audio file (wav/mp3)")
    parser.add_argument("output", help="output midi file (.mid)")
    parser.add_argument("--sr", type=int, default=16000)
    parser.add_argument("--fmin", type=float, default=65.0)
    parser.add_argument("--fmax", type=float, default=2093.0)
    parser.add_argument("--hop", type=int, default=256)
    parser.add_argument("--tempo", type=float, default=0.0, help="BPM; 0で音源から自動推定")
    parser.add_argument("--accuracy", choices=ACCURACY_PRESETS, default="normal")
    args = parser.parse_args()

    transcribe(args.input, args.output, sr=args.sr, fmin=args.fmin, fmax=args.fmax, hop_length=args.hop, tempo=args.tempo, accuracy=args.accuracy)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
