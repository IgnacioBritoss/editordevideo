import os
import hashlib
import colorsys
import requests
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

CACHE_DIR = Path("/tmp/editordevideo_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_google_quota_exhausted = False


def _get_keys():
    return (
        os.getenv("GOOGLE_API_KEY", ""),
        os.getenv("GOOGLE_CX", ""),
        os.getenv("PEXELS_API_KEY", ""),
    )


def fetch_image(keyword: str, query: str = "") -> str:
    """
    Returns local path to an image for the given keyword/query.
    Order: Google → Pexels → generated gradient fallback.
    Always returns a valid path.
    """
    global _google_quota_exhausted

    search_term = query if query else keyword
    cache_key = hashlib.md5(search_term.lower().encode()).hexdigest()[:12]
    cached = CACHE_DIR / f"{cache_key}.jpg"
    if cached.exists():
        return str(cached)

    google_key, google_cx, pexels_key = _get_keys()
    url = None

    if google_key and google_cx and not _google_quota_exhausted:
        url, exhausted = _google_search(search_term, google_key, google_cx)
        if exhausted:
            _google_quota_exhausted = True

    if not url and pexels_key:
        url = _pexels_search(search_term, pexels_key) or _pexels_search(keyword, pexels_key)

    if url:
        path = _download(url, cached)
        if path:
            return path

    return _generate_fallback(keyword, cached)


def _google_search(query: str, api_key: str, cx: str) -> tuple:
    try:
        r = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": api_key,
                "cx": cx,
                "q": query,
                "searchType": "image",
                "num": 3,
                "imgSize": "large",
                "imgType": "photo",
                "safe": "active",
            },
            timeout=8,
        )
        data = r.json()

        if r.status_code == 429 or "rateLimitExceeded" in str(data.get("error", "")):
            return None, True
        if r.status_code == 400 and "quota" in str(data.get("error", "")).lower():
            return None, True

        items = data.get("items", [])
        if items:
            return items[0]["link"], False
    except Exception:
        pass
    return None, False


def _pexels_search(query: str, api_key: str) -> str | None:
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            params={"query": query, "per_page": 3, "orientation": "landscape"},
            headers={"Authorization": api_key},
            timeout=8,
        )
        photos = r.json().get("photos", [])
        if photos:
            return photos[0]["src"]["large"]
    except Exception:
        pass
    return None


def _download(url: str, dest: Path) -> str | None:
    try:
        r = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0"},
            stream=True,
        )
        if r.status_code == 200:
            dest.write_bytes(r.content)
            # Validate it's actually an image
            Image.open(dest).verify()
            return str(dest)
    except Exception:
        dest.unlink(missing_ok=True)
    return None


def _hsl_to_rgb(h: float, s: float, l: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return int(r * 255), int(g * 255), int(b * 255)


def _generate_fallback(keyword: str, dest: Path) -> str:
    """Generate a colorful gradient image with the keyword as large text."""
    W, H = 1280, 720
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    seed = int(hashlib.md5(keyword.encode()).hexdigest()[:6], 16)
    hue1 = (seed % 360) / 360.0
    hue2 = (hue1 + 0.35) % 1.0
    c1 = _hsl_to_rgb(hue1, 0.75, 0.18)
    c2 = _hsl_to_rgb(hue2, 0.80, 0.10)

    for y in range(H):
        t = y / H
        r = int(c1[0] * (1 - t) + c2[0] * t)
        g = int(c1[1] * (1 - t) + c2[1] * t)
        b = int(c1[2] * (1 - t) + c2[2] * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Try to load a decent font, fall back to PIL default
    font = None
    font_size = 96
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]:
        try:
            font = ImageFont.truetype(path, font_size)
            break
        except Exception:
            continue

    text = keyword.upper()

    if font:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        while tw > W - 80 and font_size > 24:
            font_size -= 8
            font = ImageFont.truetype(font.path, font_size)
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (W - tw) / 2 - bbox[0]
        y = (H - th) / 2 - bbox[1]
        # Shadow
        draw.text((x + 4, y + 4), text, fill=(0, 0, 0, 120), font=font)
        draw.text((x, y), text, fill=(255, 255, 255), font=font)
    else:
        draw.text((W // 2, H // 2), text, fill=(255, 255, 255), anchor="mm")

    img.save(str(dest), "JPEG", quality=88)
    return str(dest)
