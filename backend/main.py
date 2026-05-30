import os
import uuid
import shutil
import traceback
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

from transcriber import transcribe
from keywords import get_segments_with_keywords
from image_fetcher import fetch_image
from video_maker import make_video

app = FastAPI(title="Editor de Video")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("/tmp/editordevideo_uploads")
OUTPUT_DIR = Path("/tmp/editordevideo_outputs")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# In-memory job store: job_id -> {status, progress, message, output_path}
jobs: dict[str, dict] = {}


def _set(job_id: str, **kwargs):
    jobs[job_id].update(kwargs)


def process(job_id: str, audio_path: str):
    try:
        _set(job_id, status="processing", progress=5, message="Transcribiendo audio...")

        words = transcribe(audio_path)
        if not words:
            raise ValueError("No se pudo transcribir el audio.")

        _set(job_id, progress=30, message="Extrayendo palabras clave...")

        segments = get_segments_with_keywords(words, segment_duration=3.0)

        _set(job_id, progress=38, message=f"Buscando {len(segments)} imágenes...")

        for i, seg in enumerate(segments):
            kw = seg["keyword"]
            query = seg.get("query", kw)
            img = fetch_image(kw, query)
            seg["image_path"] = img
            pct = 38 + int((i + 1) / len(segments) * 42)
            _set(job_id, progress=pct, message=f"Imágenes: {i+1}/{len(segments)} — {query}")

        _set(job_id, progress=82, message="Armando video...")

        output_path = str(OUTPUT_DIR / f"{job_id}.mp4")
        make_video(audio_path, segments, output_path)

        _set(
            job_id,
            status="done",
            progress=100,
            message="¡Video listo!",
            output_path=output_path,
        )

    except Exception as e:
        _set(job_id, status="error", progress=0, message=str(e))
        traceback.print_exc()

    finally:
        # Clean up uploaded audio file
        try:
            os.unlink(audio_path)
        except Exception:
            pass


@app.post("/upload")
async def upload(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())
    ext = Path(file.filename or "audio.mp3").suffix or ".mp3"
    audio_path = str(UPLOAD_DIR / f"{job_id}{ext}")

    with open(audio_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    jobs[job_id] = {"status": "queued", "progress": 0, "message": "En cola..."}
    background_tasks.add_task(process, job_id, audio_path)

    return {"job_id": job_id}


@app.get("/status/{job_id}")
def status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return JSONResponse({"error": "Job no encontrado"}, status_code=404)
    return job


@app.get("/download/{job_id}")
def download(job_id: str):
    job = jobs.get(job_id)
    if not job or job.get("status") != "done":
        return JSONResponse({"error": "Video no disponible"}, status_code=404)
    return FileResponse(
        job["output_path"],
        media_type="video/mp4",
        filename="video.mp4",
        headers={"Accept-Ranges": "bytes"},
    )


@app.get("/health")
def health():
    return {"ok": True}
