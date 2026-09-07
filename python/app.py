#!/usr/bin/env python3
"""Local web UI for the Audio2MIDI prototype."""
import shutil
import sys
import tempfile
import threading
import uuid
from io import BytesIO
from pathlib import Path

from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename

from separation import separate_stems
from transcribe import ACCURACY_PRESETS, _resolve_tempo, transcribe, transcribe_stems

def resource_path(relative_path):
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_path / relative_path


app = Flask(__name__, template_folder=str(resource_path("templates")))
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024
ALLOWED_EXTENSIONS = {"wav", "mp3", "flac", "ogg", "m4a"}
JOBS = {}
JOBS_LOCK = threading.Lock()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.get("/")
def index():
    return render_template("index.html")


def update_job(job_id, **values):
    with JOBS_LOCK:
        JOBS[job_id].update(values)


def process_job(job_id, input_path, output_path, work_dir, settings, mode):
    try:
        if settings["tempo"] <= 0:
            settings["tempo"] = _resolve_tempo(input_path, 0, settings["sr"])
        update_job(job_id, progress=10, message="音源を分離しています...")
        if mode == "single":
            transcribe(input_path, output_path, **settings)
            update_job(job_id, progress=95, message="MIDIファイルを書き出しています...")
        else:
            stems = separate_stems(input_path, Path(work_dir) / "stems")
            update_job(job_id, progress=55, message="楽器ごとのMIDIを解析しています...")

            def report_transcription_progress(ratio):
                update_job(job_id, progress=55 + int(ratio * 40), message="楽器ごとのMIDIを解析しています...")

            transcribe_stems(stems, output_path, progress=report_transcription_progress, **settings)
        with open(output_path, "rb") as midi_file:
            midi_data = midi_file.read()
        output_name = f"{Path(JOBS[job_id]['source_name']).stem or 'transcribed'}.mid"
        update_job(job_id, progress=100, status="completed", message="変換が完了しました。", data=midi_data, output_name=output_name)
    except Exception as error:
        app.logger.exception("Transcription failed")
        update_job(job_id, status="error", message=f"変換に失敗しました: {error}")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


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
        tempo = float(request.form.get("tempo", 0.0))
        accuracy = request.form.get("accuracy", "normal")
        if sr <= 0 or fmin <= 0 or fmax <= fmin or hop_length <= 0 or tempo < 0 or accuracy not in ACCURACY_PRESETS:
            raise ValueError
    except ValueError:
        return {"error": "設定値を確認してください。"}, 400

    input_suffix = Path(secure_filename(audio.filename)).suffix.lower()
    work_dir = tempfile.mkdtemp(prefix="audio2midi-")
    input_path = Path(work_dir) / f"input{input_suffix}"
    output_path = Path(work_dir) / "transcribed.mid"
    audio.save(input_path)
    job_id = uuid.uuid4().hex
    settings = {"sr": sr, "fmin": fmin, "fmax": fmax, "hop_length": hop_length, "tempo": tempo, "accuracy": accuracy}
    with JOBS_LOCK:
        JOBS[job_id] = {
            "status": "running",
            "progress": 5,
            "message": "変換を準備しています...",
            "source_name": secure_filename(audio.filename),
        }
    thread = threading.Thread(
        target=process_job,
        args=(job_id, input_path, output_path, work_dir, settings, request.form.get("mode", "multitrack")),
        daemon=True,
    )
    thread.start()
    return {"job_id": job_id}, 202


@app.get("/progress/<job_id>")
def job_progress(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return {"error": "ジョブが見つかりません。"}, 404
        return {key: value for key, value in job.items() if key not in {"data", "source_name"}}


@app.get("/download/<job_id>")
def download_result(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None or job.get("status") != "completed":
            return {"error": "変換結果がまだ準備できていません。"}, 404
        midi_data = job["data"]
        output_name = job["output_name"]
        del JOBS[job_id]
    return send_file(BytesIO(midi_data), as_attachment=True, download_name=output_name, mimetype="audio/midi")


if __name__ == "__main__":
    frozen = getattr(sys, "frozen", False)
    if frozen:
        from waitress import serve

        serve(app, host="127.0.0.1", port=5000)
    else:
        app.run(host="127.0.0.1", port=5000, debug=True)
