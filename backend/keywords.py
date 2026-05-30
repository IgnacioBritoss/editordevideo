import re
from collections import Counter

STOP_WORDS = {
    # Spanish
    "a", "al", "algo", "algunas", "algunos", "ante", "antes", "como", "con",
    "contra", "cual", "cuando", "de", "del", "desde", "donde", "durante",
    "e", "el", "ella", "ellas", "ellos", "en", "entre", "era", "erais",
    "eran", "eras", "eres", "es", "esa", "esas", "ese", "eso", "esos",
    "esta", "estas", "este", "esto", "estos", "fue", "fueron", "fui",
    "fuimos", "ha", "han", "has", "hasta", "hay", "he", "hemos", "la",
    "las", "le", "les", "lo", "los", "me", "mi", "mis", "mucho", "muchos",
    "muy", "más", "mas", "ni", "no", "nos", "nosotras", "nosotros", "o",
    "os", "otra", "otras", "otro", "otros", "para", "pero", "por",
    "porque", "que", "quien", "quienes", "se", "ser", "si", "sin",
    "sobre", "su", "sus", "también", "tambien", "tan", "tanto", "te",
    "tengo", "ti", "tiene", "tienen", "todo", "todos", "tu", "tus",
    "un", "una", "unas", "uno", "unos", "vos", "y", "ya", "yo",
    "del", "con", "por", "sin", "bajo", "durante", "mediante", "según",
    "segun", "hacia", "tras", "mediante", "ante", "bajo", "cabe",
    "sobre", "entre", "hasta", "para", "por", "sin", "so", "tras",
    "así", "asi", "bien", "entonces", "luego", "nunca", "siempre",
    "además", "ademas", "pues", "aunque", "ahora", "aquí", "aqui",
    "allí", "alli", "cuando", "donde", "como", "porque", "mientras",
    "propio", "propia", "propios", "propias", "cada", "todo", "toda",
    "hacer", "hecho", "haber", "tiene", "tener", "puede", "poder",
    "debe", "deber", "decir", "dijo", "dice", "han", "ser", "estar",
    "son", "son", "somos", "estoy", "estamos", "estaba", "estaban",
    "había", "habia", "habían", "habian", "tenía", "tenia", "tenían",
    # English
    "a", "about", "above", "after", "again", "against", "all", "am",
    "an", "and", "any", "are", "as", "at", "be", "because", "been",
    "before", "being", "below", "between", "both", "but", "by", "can",
    "could", "did", "do", "does", "doing", "down", "during", "each",
    "few", "for", "from", "further", "get", "got", "had", "has", "have",
    "having", "he", "her", "here", "hers", "herself", "him", "himself",
    "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself",
    "me", "more", "most", "my", "myself", "no", "nor", "not", "of",
    "off", "on", "once", "only", "or", "other", "our", "ours",
    "ourselves", "out", "over", "own", "same", "she", "should", "so",
    "some", "such", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "this", "those",
    "through", "to", "too", "under", "until", "up", "very", "was", "we",
    "were", "what", "when", "where", "which", "while", "who", "whom",
    "why", "with", "would", "you", "your", "yours", "yourself",
    "yourselves", "also", "just", "like", "said", "say", "says",
    "will", "been", "can", "may", "might", "shall", "must", "need",
    "dare", "ought", "used",
}

_CLEAN_RE = re.compile(r"[^a-zA-ZáéíóúüñÁÉÍÓÚÜÑàèìòùÀÈÌÒÙ]")


def _clean(w: str) -> str:
    return _CLEAN_RE.sub("", w)


def get_segments_with_keywords(
    words: list[dict], segment_duration: float = 5.0
) -> list[dict]:
    """
    Groups words into fixed time windows and returns:
    [{start, end, keyword, context}]
    """
    if not words:
        return []

    total = words[-1]["end"]
    segments = []
    t = 0.0

    while t < total:
        end = min(t + segment_duration, total)
        seg_words = [w for w in words if t <= w["start"] < end]
        kw = _best_keyword(seg_words)
        context = " ".join(w["word"] for w in seg_words)
        segments.append({"start": t, "end": end, "keyword": kw, "context": context})
        t = end

    return segments


def _best_keyword(words: list[dict]) -> str:
    texts = [w["word"] for w in words]
    scored: list[tuple[str, float]] = []

    for i, raw in enumerate(texts):
        clean = _clean(raw)
        if not clean or len(clean) < 3:
            continue
        if clean.lower() in STOP_WORDS:
            continue

        score = 0.0
        # Proper nouns get highest priority
        if clean[0].isupper() and i > 0:
            score += 4.0
        # Longer words = more specific
        score += min(len(clean) / 4.0, 2.5)
        # Avoid duplicates with previous keyword (small penalty)
        scored.append((clean, score))

    if not scored:
        # Fallback: just use non-stop words
        fallback = [_clean(w) for w in texts if len(_clean(w)) >= 3]
        return fallback[0] if fallback else "abstract"

    scored.sort(key=lambda x: -x[1])

    # Deduplicate: pick highest scored unique word
    seen = set()
    for word, _ in scored:
        low = word.lower()
        if low not in seen:
            seen.add(low)
            return word

    return scored[0][0]
