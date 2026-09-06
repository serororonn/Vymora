#!/usr/bin/env python3
"""Local web UI for the Audio2MIDI prototype."""
import os
import tempfile
from io import BytesIO
from pathlib import Path

from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename

from transcribe import transcribe

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024
ALLOWED_EXTENSIONS = {"wav", "mp3", "flac", "ogg", "m4a"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/transcribe")
def create_midi():
    audio = request.files.get("audio")
    if audio is None or not audio.filename:
        return {"error": "音声ファイルを選択してください。"}, 400
    if not allowed_file(audio.filename):
        return {"error": "WAV、MP3、FLAC、OGG、M4Aに対応しています。"}, 400

    try:
        sr = int(request.form.get("sr", 16000))
        fmin = float(request.form.get("fmin", 65.0))
        fmax = float(request.form.get("fmax", 2093.0))
        hop_length = int(request.form.get("hop", 256))
        if sr <= 0 or fmin <= 0 or fmax <= fmin or hop_length <= 0:
            raise ValueError
    except ValueError:
        return {"error": "設定値を確認してください。"}, 400

    input_suffix = Path(secure_filename(audio.filename)).suffix.lower()
    input_file = tempfile.NamedTemporaryFile(delete=False, suffix=input_suffix)
    output_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mid")
    input_path = input_file.name
    output_path = output_file.name
    input_file.close()
    output_file.close()

    try:
        audio.save(input_path)
        transcribe(input_path, output_path, sr=sr, fmin=fmin, fmax=fmax, hop_length=hop_length)
    except Exception as error:
        for path in (input_path, output_path):
            try:
                os.remove(path)
            except OSError:
                pass
        app.logger.exception("Transcription failed")
        return {"error": f"変換に失敗しました: {error}"}, 500

    output_name = f"{Path(secure_filename(audio.filename)).stem or 'transcribed'}.mid"
    with open(output_path, "rb") as midi_file:
        midi_data = midi_file.read()
    for path in (input_path, output_path):
        try:
            os.remove(path)
        except OSError:
            pass
    return send_file(BytesIO(midi_data), as_attachment=True, download_name=output_name, mimetype="audio/midi")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
