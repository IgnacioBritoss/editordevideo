import re

STOP_WORDS = {
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
    "segun", "hacia", "tras", "ante", "cabe", "así", "asi", "bien",
    "entonces", "luego", "nunca", "siempre", "además", "ademas", "pues",
    "aunque", "ahora", "aquí", "aqui", "allí", "alli", "mientras",
    "propio", "propia", "propios", "propias", "cada", "todo", "toda",
    "hacer", "hecho", "haber", "tener", "puede", "poder", "debe", "deber",
    "decir", "dijo", "dice", "estar", "son", "somos", "estoy", "estamos",
    "estaba", "estaban", "había", "habia", "tenía", "tenia",
    "about", "above", "after", "again", "against", "all", "am", "an",
    "and", "any", "are", "as", "at", "be", "because", "been", "before",
    "being", "below", "between", "both", "but", "by", "can", "could",
    "did", "do", "does", "doing", "down", "during", "each", "few", "for",
    "from", "further", "get", "got", "had", "has", "have", "having",
    "he", "her", "here", "hers", "herself", "him", "himself", "his",
    "how", "if", "in", "into", "is", "it", "its", "itself", "me",
    "more", "most", "my", "myself", "nor", "not", "of", "off", "on",
    "once", "only", "or", "other", "our", "ours", "ourselves", "out",
    "over", "own", "same", "she", "should", "so", "some", "such",
    "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "we", "were", "what",
    "when", "where", "which", "while", "who", "whom", "why", "with",
    "would", "you", "your", "yours", "yourself", "yourselves",
    "also", "just", "like", "said", "say", "says", "will", "may",
    "might", "shall", "must", "need", "i",
}

_CLEAN_RE = re.compile(r"[^a-zA-ZáéíóúüñÁÉÍÓÚÜÑàèìòùÀÈÌÒÙ]")


def _clean(w: str) -> str:
    return _CLEAN_RE.sub("", w)


def get_segments_with_keywords(
    words: list[dict], segment_duration: float = 3.0
) -> list[dict]:
    """
    Groups words into time windows and returns [{start, end, keyword, query}].
    Uses 3-second windows for more granular image changes.
    """
    if not words:
        return []

    total = words[-1]["end"]
    segments = []
    t = 0.0

    while t < total:
        end = min(t + segment_duration, total)
        seg_words = [w for w in words if t <= w["start"] < end]
        keyword, query = _best_keyword_and_query(seg_words)
        segments.append({
            "start": t,
            "end": end,
            "keyword": keyword,
            "query": query,
            "context": " ".join(w["word"] for w in seg_words),
        })
        t = end

    # Merge consecutive identical queries to avoid redundant image fetches
    merged = []
    for seg in segments:
        if merged and merged[-1]["query"] == seg["query"]:
            merged[-1]["end"] = seg["end"]
        else:
            merged.append(dict(seg))

    return merged


def _best_keyword_and_query(words: list[dict]) -> tuple[str, str]:
    """
    Returns (keyword, search_query).
    Proper nouns get highest priority, then concrete nouns.
    Multi-word phrases (e.g. 'cafe con leche') are detected too.
    """
    texts = [w["word"] for w in words]

    # --- Pass 1: collect proper nouns (capitalized, not first word) ---
    proper_nouns = []
    for i, raw in enumerate(texts):
        clean = _clean(raw)
        if not clean or len(clean) < 2:
            continue
        if clean[0].isupper() and i > 0 and clean.lower() not in STOP_WORDS:
            proper_nouns.append(clean)

    # If we found proper nouns, join consecutive ones (e.g. "Cristiano Ronaldo")
    if proper_nouns:
        # Try to find multi-word proper noun sequences
        phrase = _find_proper_noun_phrase(texts)
        if phrase:
            return phrase, phrase
        return proper_nouns[0], proper_nouns[0]

    # --- Pass 2: concrete nouns — longer words, not stop words ---
    candidates = []
    for raw in texts:
        clean = _clean(raw)
        if not clean or len(clean) < 3:
            continue
        if clean.lower() in STOP_WORDS:
            continue
        candidates.append(clean)

    if not candidates:
        fallback = [_clean(w) for w in texts if len(_clean(w)) >= 3]
        kw = fallback[0] if fallback else "abstract"
        return kw, kw

    # Pick longest (most specific) candidate
    candidates.sort(key=lambda x: -len(x))
    keyword = candidates[0]

    # Build a richer query: keyword + up to 1 more concrete word
    query_parts = [keyword]
    for c in candidates[1:3]:
        if c.lower() != keyword.lower():
            query_parts.append(c)
            break

    return keyword, " ".join(query_parts)


def _find_proper_noun_phrase(texts: list[str]) -> str:
    """Find sequences of capitalized words (e.g. 'Cristiano Ronaldo')."""
    phrases = []
    current = []
    for i, raw in enumerate(texts):
        clean = _clean(raw)
        if clean and clean[0].isupper() and i > 0 and clean.lower() not in STOP_WORDS:
            current.append(clean)
        else:
            if len(current) >= 2:
                phrases.append(" ".join(current))
            current = []
    if len(current) >= 2:
        phrases.append(" ".join(current))

    return phrases[0] if phrases else ""
