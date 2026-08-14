import hashlib
import re


def _tokenize(text: str) -> list[str]:
    """Tokenize text. Uses character bigrams for CJK, words for others."""
    tokens = []
    # Split into segments of CJK and non-CJK
    segments = re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]+|[a-zA-Z0-9]+', text)
    for seg in segments:
        if re.match(r'[\u4e00-\u9fff\u3400-\u4dbf]', seg):
            # CJK: use character bigrams
            for i in range(len(seg) - 1):
                tokens.append(seg[i:i+2])
        else:
            tokens.append(seg.lower())
    return tokens


def simhash(text: str, hash_bits: int = 64) -> int:
    """Compute a simhash fingerprint for the given text.
    Supports CJK text via character bigrams.
    """
    if not text:
        return 0

    tokens = _tokenize(text)
    if not tokens:
        return 0

    v = [0] * hash_bits

    for token in tokens:
        token_hash = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        for i in range(hash_bits):
            if token_hash & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1

    fingerprint = 0
    for i in range(hash_bits):
        if v[i] > 0:
            fingerprint |= (1 << i)

    return fingerprint


def hamming_distance(a: int, b: int) -> int:
    """Compute the Hamming distance between two integers."""
    return bin(a ^ b).count("1")


def fingerprint_text(title: str, content: str | None) -> str:
    """Generate a simhash fingerprint string for dedup.
    Uses title + first 500 chars of content as specified in PRD.
    """
    text = title
    if content:
        text += " " + content[:500]
    fp = simhash(text)
    return format(fp, "016x")


def is_near_duplicate(fp1: str, fp2: str, threshold: int = 3) -> bool:
    """Check if two fingerprints are near-duplicates (hamming distance < threshold)."""
    if not fp1 or not fp2:
        return False
    return hamming_distance(int(fp1, 16), int(fp2, 16)) < threshold
