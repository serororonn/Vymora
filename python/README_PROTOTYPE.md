# Audio2MIDI プロトタイプ（バッチ CLI）

このディレクトリには、音源分離を使って楽器別のMIDIを生成するAudio2MIDIプロトタイプが含まれます。

要点:
- 入力: WAV/MP3
- 出力: 標準 MIDI (`.mid`)
- 実装: `separation.py`（Demucsによる音源分離）、`transcribe.py`（librosa の `pyin` によるピッチ抽出）

セットアップ例:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

実行例:

```powershell
python transcribe.py path\to\input.wav path\to\output.mid
```

ローカルWebで起動:

```powershell
pip install -r requirements.txt
python app.py
```

ブラウザで `http://127.0.0.1:5000` を開き、音声ファイルを選択してください。

標準のマルチトラックモードでは、ボーカル、ベース、ギター、ピアノ、その他に加え、ドラムをキック、スネア、ハイハットへ分けた8トラックのMIDIを生成します。初回はDemucsモデルのダウンロードが必要です。ドラムの分類は簡易推定です。ギター、ピアノ、その他は現在単音ピッチ推定なので、複雑な和音の精度には限界があります。生成後にDAWで音色、音域、ノート、トラック構成を編集する前提の出力です。

注意:
- 本プロトタイプは研究/実験目的の簡易実装です。実運用/DAW内リアルタイム用途では、モデルの最適化、量子化、C++/JUCE プラグイン化が必要です。
