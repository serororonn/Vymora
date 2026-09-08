# Audio2MIDI ローカルWeb版

音源を楽器別に分離し、DAWで編集できるマルチトラックMIDIへ変換する試作実装です。最終的な音色、ノート、タイミング、奏法はDAWで調整する前提です。

## 出力トラック

標準のマルチトラックモードでは、次の8トラックを1つのMIDIファイルへ出力します。

- Vocals
- Bass
- Guitar
- Piano
- Other
- Kick
- Snare
- Hi-Hat

Demucsの6ステムを使い、ドラムステムはオンセットとスペクトル特徴からKick、Snare、Hi-Hatへ分割します。

生成後は原曲忠実モードで、4小節単位のセクション/コード解析、明確なドラムの1打抜け補完、ベースの明白な音域外・重複補正を行います。原曲にないメロディやコードは生成しません。解析結果はMIDIの`Structure Analysis`トラックにマーカーとして出力します。

## セットアップ

Basic Pitchの高精度推定を使う場合はPython 3.10を使用します。PowerShellで実行します。

```powershell
Set-Location .\python
py -3.10 -m venv .venv310
.\.venv310\Scripts\Activate.ps1
pip install -r requirements.txt
```

初回のマルチトラック変換ではDemucsモデルをダウンロードします。

## Web版の起動

```powershell
python app.py
```

ブラウザで http://127.0.0.1:5000 を開き、音声ファイルを選択します。

変換はバックグラウンドジョブとして実行されます。画面には分離、解析、MIDI書き出しの進捗率が表示されます。

APIの概要:

- `POST /transcribe`: 音声を受け付け、`job_id`を返す
- `GET /progress/<job_id>`: 進捗と状態を返す
- `GET /download/<job_id>`: 完了したMIDIを返す

## 変換方式

```text
音声
  -> Demucsでステム分離
  -> ステムごとのポリフォニック音高推定
  -> ドラムイベント分類
  -> 8トラックMIDI生成
```

Python 3.10とTensorFlowが導入された環境では、各ステムへBasic Pitchを個別に実行します。利用できない場合は、librosaの複数ピーク解析へ自動フォールバックします。単一トラック（高速）モードではlibrosa.pyinを使用します。テンポを0にすると音源からBPMを自動推定します。

検出の強さは「強め」「普通」「弱め」から選べます。強めは音符の取りこぼしを減らし、弱めは誤検出を減らします。

## 精度評価

推定結果を改善するには、同じ音源と正確に採譜した正解MIDIを用意します。推定MIDIを音源化しただけでは正解MIDIにはなりません。

```powershell
python evaluate.py estimated.mid reference.mid
```

出力される主な指標:

- `precision`: 推定ノートのうち正しい割合
- `recall`: 正解ノートを拾えた割合
- `f1`: precisionとrecallの調和平均
- `tracks`: 楽器別のprecision、recall、F1
- `offset_f1`: 発音終了時刻も一致した場合のF1
- 発音時刻の平均誤差
- 音長の平均誤差
- ベロシティの平均誤差

ノートは同じトラック内で音高と発音時刻を使って一対一に対応付けます。許容範囲は`--onset-tolerance`、`--offset-tolerance`、`--pitch-tolerance`で変更できます。

## CLI

従来の単一トラック変換は次で実行できます。

```powershell
python transcribe.py input.wav output.mid
```

CLIでも検出強度を指定できます。

```powershell
python transcribe.py input.wav output.mid --accuracy strong
```

## 制約

- Demucsの`Other`ステムをストリングス、シンセ、サックスなどへ完全分離する機能はありません。
- ギターやピアノの複雑な和音、ボーカルのビブラート、ギターの弦・フレット・奏法、ピアノのペダルは完全には復元できません。
- Basic Pitchは環境によってTensorFlowの依存制約があります。未導入時は複数ピーク解析へフォールバックします。
- 研究・試作段階であり、商用利用前に精度評価、モデルライセンス、性能、クラッシュ復旧、exe配布を確認してください。

## 将来のexe化

Windows版では、モデルファイルを含む配布構成、PyInstallerのhidden imports、Torch/Demucsのサイズ、初回モデル配置、GPU有無の判定を検証する必要があります。exe化は依存関係とモデルライセンスを確認してから行います。
