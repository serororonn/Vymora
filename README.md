# Vymora Audio2MIDI

音源を楽器別に分離し、DAWで編集できる標準MIDIへ変換するローカル音楽制作ツールです。変換結果は完成品ではなく、耳コピ・編曲の下書きとして使い、最終調整をDAWで行う設計です。

## 現在できること

- WAV / MP3 / FLAC / OGG / M4Aを入力
- Demucsで音源をステム分離
- 8本のMIDIトラックを生成
- 変換中の進捗率をブラウザに表示
- MIDIをDAWへ読み込み可能な`.mid`としてダウンロード
- 推定MIDIと正解MIDIの精度を数値比較

生成トラック:

1. Vocals
2. Bass
3. Guitar
4. Piano
5. Other
6. Kick
7. Snare
8. Hi-Hat

ドラムはDemucsのドラムステムをオンセットとスペクトル特徴から3種類へ分類します。生成後は原曲忠実モードで、セクション/コード解析、明確なドラムの1打抜け補完、ベースの明白な音域外・重複補正を行います。

## 起動

PowerShellで次を実行します。

```powershell
Set-Location .\python
py -3.10 -m venv .venv310
.\.venv310\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

ブラウザで http://127.0.0.1:5000 を開きます。

出力MIDIにはDAWで確認できる`Structure Analysis`トラックが追加されます。4小節ごとのセクション、密度、推定コードを示すマーカーです。原曲にないメロディやコードは生成しません。
Python 3.10とTensorFlowが利用できる環境ではBasic Pitchを使います。利用できない環境では、librosaの複数ピーク解析へ自動フォールバックします。単一トラックの高速モードでは、従来のpyinによる単音推定を使います。テンポを0にすると音源からBPMを自動推定します。多重音源では単一トラックよりマルチトラックモードを使用してください。

検出の強さは「強め」「普通」「弱め」から選べます。強めは音符の取りこぼしを減らし、弱めは誤検出を減らします。今回の比較曲では強めがF1最高、弱めがPrecision最高でした。

曲タイプは「自動」「ボカロ・合成音声」「シンセ中心」「バンド」から選べます。ボカロは声域と短い音符、シンセは和音と同時発音数を補正します。曲タイプはジャンル名ではなく、主な音源構成に合わせて選択してください。

初回のマルチトラック変換ではDemucsモデルのダウンロードが発生します。音源の長さ、CPU/GPU、ストレージ速度により処理時間が変わります。

## Windows exeの作成

Python 3.10の仮想環境を用意した後、PowerShellで次を実行します。

```powershell
Set-Location .\python
py -3.10 -m venv .venv310
.\.venv310\Scripts\Activate.ps1
.\build_exe.ps1
```

生成物は `python\dist\Vymora.exe` です。exeを起動した後、ブラウザで http://127.0.0.1:5000 を開きます。初回のマルチトラック変換ではDemucsモデルのダウンロードが発生します。

## 変換方式

```text
音源
  -> Demucsによるステム分離
  -> ステムごとの音高・発音時刻推定
  -> 楽器別MIDIトラック生成
  -> 1つのMIDIファイルへ統合
```

ポリフォニック推定器が利用できる環境ではBasic Pitchを使います。利用できない環境では、librosaの複数ピーク解析へ自動フォールバックします。単一トラックの高速モードでは、従来のpyinによる単音推定を使います。テンポを0にすると音源からBPMを自動推定します。多重音源では単一トラックよりマルチトラックモードを使用してください。

## 精度評価

精度を改善するには、同じ音源と、その音源を正確に採譜した正解MIDIの組が必要です。推定MIDIを音源化しただけでは正解データにはなりません。

```powershell
Set-Location .\python
python evaluate.py estimated.mid reference.mid
```

評価結果には、全体の`precision`、`recall`、`f1`に加えて、トラック別の指標が`tracks`として含まれます。ノートは楽器名、音高、発音時刻で一対一に対応付けられ、別トラックのノートは一致しません。
`offset_precision`、`offset_recall`、`offset_f1`は、発音終了時刻も許容範囲内だったノートだけを数える指標です。許容範囲は次のように変更できます。

```powershell
python evaluate.py estimated.mid reference.mid --onset-tolerance 0.05 --offset-tolerance 0.1 --pitch-tolerance 0
```

実音源の評価セットを増やし、楽器別に数値を比較してからモデルや閾値を変更します。

## ファイル構成

```text
python/
  app.py                 ローカルWebサーバーとジョブAPI
  separation.py         Demucsによる音源分離
  transcribe.py         楽器別MIDI生成とドラム分割
  arrange_midi.py       構造解析と原曲忠実の後処理
  evaluate.py           推定MIDIと正解MIDIの比較
  templates/index.html  Web UI
  requirements.txt      Python依存関係
```

## 商用化に向けた残作業

このリポジトリは研究・試作段階です。商用品質にするには、実データでの評価セット作成、楽器別モデルの選定、誤検出・重複ノートの後処理、GPU/CPU性能検証、モデルライセンス確認、ログとキャンセル処理、PyInstaller等によるexe化が必要です。

Demucsの`Other`ステムをストリングス、シンセ、サックスなどへ完全分離する機能はまだありません。また、ギターの弦・フレット・奏法、ピアノのペダル、ボーカルのビブラートなどはMIDIだけでは完全には復元できません。

## ライセンス

プロジェクトのライセンスは確定前です。依存モデルとライブラリのライセンスを確認してから配布形態を決定します。
