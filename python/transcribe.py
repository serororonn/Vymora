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


INSTRUMENTS = {
    "vocals": (53, "Vocals"),
    "bass": (33, "Bass"),
    "guitar": (24, "Guitar"),
    "piano": (0, "Piano"),
    "drums": (0, "Drums"),
    "other": (48, "Other"),
}


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


def transcribe_instrument(input_path, instrument_name, sr=16000, fmin=65.0, fmax=2093.0, hop_length=256):
    if instrument_name == "drums":
        raise ValueError("drums must be expanded into individual drum tracks")
    program, track_name = INSTRUMENTS[instrument_name]
    y, sr = librosa.load(input_path, sr=sr, mono=True)

    # 基本ピッチ推定（librosa.pyin）
    f0, voiced_flag, voiced_prob = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr, hop_length=hop_length)
    frames = np.arange(len(f0))
    times = librosa.frames_to_time(frames, sr=sr, hop_length=hop_length)

    instrument = pretty_midi.Instrument(program=program, name=track_name)

    n_frames = len(f0)
    i = 0
    # 連続した有声音部分をノートとしてまとめる簡易ロジック
    while i < n_frames:
        if not np.isfinite(f0[i]):
            i += 1
            continue
        start = times[i]
        freqs = []
        amps = []
        j = i
        while j < n_frames and np.isfinite(f0[j]):
            freqs.append(f0[j])
            frame_start = int(j * hop_length)
            frame_end = min(len(y), frame_start + hop_length)
            frame = y[frame_start:frame_end]
            amp = np.sqrt(np.mean(frame ** 2)) if len(frame) > 0 else 0.0
            amps.append(amp)
            j += 1
        end = times[j - 1] + (hop_length / sr)
        median_freq = float(np.median(freqs))
        pitch = int(np.round(librosa.hz_to_midi(median_freq)))
        # 簡易ベロシティ: セグメントの振幅に基づくスケーリング
        max_amp = max(amps) if amps else 1e-6
        mean_amp = float(np.mean(amps)) if amps else 0.0
        velocity = int(np.clip((mean_amp / (max_amp + 1e-9)) * 120 + 7, 1, 127))
        note = pretty_midi.Note(velocity=velocity, pitch=pitch, start=start, end=end)
        instrument.notes.append(note)
        i = j

    return instrument


def transcribe(input_path, output_path, sr=16000, fmin=65.0, fmax=2093.0, hop_length=256):
    pm = pretty_midi.PrettyMIDI()
    pm.instruments.append(
        transcribe_instrument(input_path, "piano", sr=sr, fmin=fmin, fmax=fmax, hop_length=hop_length)
    )
    pm.write(output_path)


def transcribe_stems(stem_paths, output_path, sr=16000, fmin=65.0, fmax=2093.0, hop_length=256, progress=None):
    pm = pretty_midi.PrettyMIDI()
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
            pm.instruments.append(
                transcribe_instrument(
                    stem_path,
                    instrument_name,
                    sr=sr,
                    fmin=fmin,
                    fmax=fmax,
                    hop_length=hop_length,
                )
            )
            completed_tracks += 1
        if progress is not None:
            progress(completed_tracks / track_count)
    pm.write(output_path)


def main():
    parser = argparse.ArgumentParser(description="Simple Audio2MIDI prototype")
    parser.add_argument("input", help="input audio file (wav/mp3)")
    parser.add_argument("output", help="output midi file (.mid)")
    parser.add_argument("--sr", type=int, default=16000)
    parser.add_argument("--fmin", type=float, default=65.0)
    parser.add_argument("--fmax", type=float, default=2093.0)
    parser.add_argument("--hop", type=int, default=256)
    args = parser.parse_args()

    transcribe(args.input, args.output, sr=args.sr, fmin=args.fmin, fmax=args.fmax, hop_length=args.hop)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
