import os
from pathlib import Path
from PIL import Image
import numpy as np
from moviepy.editor import (
    AudioFileClip,
    ImageClip,
    concatenate_videoclips,
    ColorClip,
)

TARGET_W = 1280
TARGET_H = 720
FPS = 24
FADE = 0.4


def _make_image_clip(img_path: str | None, duration: float) -> ImageClip:
    """Resize image to fill 1280×720, center-crop, with gentle Ken Burns zoom."""
    if not img_path or not os.path.exists(img_path):
        return ColorClip(size=(TARGET_W, TARGET_H), color=[10, 10, 20], duration=duration)

    try:
        pil = Image.open(img_path).convert("RGB")
        iw, ih = pil.size

        # Scale to fill target with a little extra for the zoom animation
        zoom_budget = 1.06
        scale = max(TARGET_W / iw, TARGET_H / ih) * zoom_budget
        nw, nh = int(iw * scale), int(ih * scale)
        pil = pil.resize((nw, nh), Image.LANCZOS)
        arr = np.array(pil)

        x_extra = (nw - TARGET_W) / 2
        y_extra = (nh - TARGET_H) / 2

        def make_frame(t: float) -> np.ndarray:
            # Ken Burns: gradually zoom in (move crop toward center)
            progress = t / max(duration, 0.001)
            x0 = int(x_extra * (1.0 - progress * 0.5))
            y0 = int(y_extra * (1.0 - progress * 0.5))
            x0 = max(0, min(x0, nw - TARGET_W))
            y0 = max(0, min(y0, nh - TARGET_H))
            return arr[y0 : y0 + TARGET_H, x0 : x0 + TARGET_W]

        from moviepy.editor import VideoClip
        clip = VideoClip(make_frame, duration=duration)
        clip = clip.set_fps(FPS)
        return clip

    except Exception:
        return ColorClip(size=(TARGET_W, TARGET_H), color=[10, 10, 20], duration=duration)


def make_video(
    audio_path: str,
    segments: list[dict],
    output_path: str,
    on_progress=None,
) -> str:
    audio = AudioFileClip(audio_path)
    total_duration = audio.duration

    # Extend last segment to cover full audio
    if segments:
        segments[-1]["end"] = total_duration

    clips = []
    n = len(segments)

    for i, seg in enumerate(segments):
        duration = max(seg["end"] - seg["start"], 0.1)
        clip = _make_image_clip(seg.get("image_path"), duration)

        if i == 0:
            clip = clip.fadein(FADE).fadeout(FADE)
        elif i == n - 1:
            clip = clip.crossfadein(FADE).fadeout(FADE)
        else:
            clip = clip.crossfadein(FADE).fadeout(FADE)

        clips.append(clip)
        if on_progress:
            on_progress(int((i + 1) / n * 100))

    video = concatenate_videoclips(clips, padding=-FADE, method="compose")
    video = video.set_duration(total_duration).set_audio(audio)

    video.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=str(Path(output_path).parent / "tmp_audio.m4a"),
        remove_temp=True,
        verbose=False,
        logger=None,
    )

    audio.close()
    return output_path
