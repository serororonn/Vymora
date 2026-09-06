"""Audio source separation through Demucs."""
import subprocess
import sys
from pathlib import Path


STEMS = ("vocals", "bass", "guitar", "piano", "drums", "other")


def separate_stems(input_path, output_dir, model_name="htdemucs_6s"):
    """Separate an audio file and return the requested Demucs stem paths."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "demucs",
        "--name",
        model_name,
        "--out",
        str(output_dir),
        str(input_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)

    track_dir = output_dir / model_name / Path(input_path).stem
    missing = [stem for stem in STEMS if not (track_dir / f"{stem}.wav").exists()]
    if missing:
        raise RuntimeError(f"音源分離後のステムが見つかりません: {', '.join(missing)}")
    return {stem: track_dir / f"{stem}.wav" for stem in STEMS}
