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

推定精度の比較:

```powershell
python evaluate.py estimated.mid reference.mid
```

`reference.mid` は同じ音源を正確に採譜した正解MIDIです。変換したMIDIを音源化したものだけでは正解データにならないため、音源と正解MIDIの組を用意して評価します。出力される `precision`、`recall`、`f1`、発音時刻誤差、音長誤差、ベロシティ誤差を基準に、楽器ごとの解析設定やモデルを改善します。

ローカルWebで起動:

```powershell
pip install -r requirements.txt
python app.py
```

ブラウザで `http://127.0.0.1:5000` を開き、音声ファイルを選択してください。

標準のマルチトラックモードでは、ボーカル、ベース、ギター、ピアノ、その他に加え、ドラムをキック、スネア、ハイハットへ分けた8トラックのMIDIを生成します。Demucsで各ステムを分離した後、Basic Pitchを各ステムへ個別実行するため、ギターやピアノの重なった音にも対応します。初回はDemucsとBasic Pitchのモデルダウンロードが必要です。ドラムの分類は簡易推定です。生成後にDAWで音色、音域、ノート、トラック構成を編集する前提の出力です。

高精度モードはBasic Pitch対応のPython環境ではニューラルモデルを使います。それ以外の環境では、各ステムに対して複数ピークを抽出するポリフォニック解析へフォールバックします。Basic PitchのWindows依存関係を揃えられる環境が必要なため、配布版ではモデルを同梱する設計にします。

注意:
- 本プロトタイプは研究/実験目的の簡易実装です。実運用/DAW内リアルタイム用途では、モデルの最適化、量子化、C++/JUCE プラグイン化が必要です。
