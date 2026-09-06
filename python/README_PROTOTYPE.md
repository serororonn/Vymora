# Audio2MIDI プロトタイプ（バッチ CLI）

このディレクトリには簡易的な Audio2MIDI のプロトタイプが含まれます。目的はまず音声ファイルから基本的な MIDI を生成できることです。

要点:
- 入力: WAV/MP3
- 出力: 標準 MIDI (`.mid`)
- 実装: `transcribe.py`（librosa の `pyin` を使った簡易ピッチ抽出）

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

注意:
- 本プロトタイプは研究/実験目的の簡易実装です。実運用/DAW内リアルタイム用途では、モデルの最適化、量子化、C++/JUCE プラグイン化が必要です。
