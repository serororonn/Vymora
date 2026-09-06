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


def transcribe(input_path, output_path, sr=16000, fmin=65.0, fmax=2093.0, hop_length=256):
    y, sr = librosa.load(input_path, sr=sr, mono=True)

    # 基本ピッチ推定（librosa.pyin）
    f0, voiced_flag, voiced_prob = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr, hop_length=hop_length)
    frames = np.arange(len(f0))
    times = librosa.frames_to_time(frames, sr=sr, hop_length=hop_length)

    pm = pretty_midi.PrettyMIDI()
    instrument = pretty_midi.Instrument(program=0)

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

    pm.instruments.append(instrument)
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
