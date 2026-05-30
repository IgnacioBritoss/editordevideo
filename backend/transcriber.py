import os

_local_model = None


def _get_local_model():
    global _local_model
    if _local_model is None:
        from faster_whisper import WhisperModel
        _local_model = WhisperModel("base", device="cpu", compute_type="int8")
    return _local_model


def transcribe(audio_path: str) -> list[dict]:
    """
    Returns list of {word, start, end} dicts sorted by start time.
    Uses OpenAI Whisper API if OPENAI_API_KEY is set, otherwise runs locally.
    """
    if os.getenv("OPENAI_API_KEY"):
        return _transcribe_openai(audio_path)
    return _transcribe_local(audio_path)


def _transcribe_local(audio_path: str) -> list[dict]:
    model = _get_local_model()
    segments, _ = model.transcribe(audio_path, word_timestamps=True)
    words = []
    for seg in segments:
        for w in (seg.words or []):
            word = w.word.strip()
            if word:
                words.append({"word": word, "start": w.start, "end": w.end})
    return words


def _transcribe_openai(audio_path: str) -> list[dict]:
    from openai import OpenAI
    client = OpenAI()
    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )
    return [
        {"word": w.word.strip(), "start": w.start, "end": w.end}
        for w in (result.words or [])
        if w.word.strip()
    ]
