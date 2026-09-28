"""
digits_to_word_nepali only does number -> words.
These two functions do the reverse (words -> number) manually,
for two DIFFERENT input styles:

  1. parse_nepali_words()        -> real Nepali number vocabulary
     e.g. "चार हजार चार सय चौरालीस"

  2. parse_phonetic_english()    -> English number words spelled
     phonetically in Devanagari script
     e.g. "फोर थाउजन्ड फोर हन्ड्रेड फोर्टी फोर"

Real user input is messy: nuqta dots, vowel-length variants, alternate
spellings of the same word (चौंसठ्ठी / चौंसठी / चौसट्ठी). A plain
dictionary lookup throws on any of these. normalize() strips the
cosmetic differences first, and closest_match() falls back to fuzzy
matching so near-misses still resolve instead of hard failing.
"""

import unicodedata
from difflib import get_close_matches

# Devanagari nuqta letters -> their non-nuqta base letter.
# e.g. फ़ (fa with nuqta) and फ (fa) are visually near-identical
# but are different code points people use inconsistently.
_NUQTA_MAP = {
    "\u0958": "क", "\u0959": "ख", "\u095A": "ग", "\u095B": "ज",
    "\u095C": "ड", "\u095D": "ढ", "\u095E": "फ", "\u095F": "य",
}


def normalize(word: str) -> str:
    """Strip cosmetic Unicode variation so lookups aren't spelling-sensitive."""
    word = unicodedata.normalize("NFC", word.strip())
    for nuqta, base in _NUQTA_MAP.items():
        word = word.replace(nuqta, base)
    word = word.replace("़", "")  # stray combining nuqta mark on its own
    return word


def closest_match(word: str, vocab: dict, cutoff: float = 0.75):
    """
    Exact match after normalization; if that fails, fuzzy-match against
    the known vocabulary. Returns the matched key, or None if nothing
    is close enough (caller decides whether that's fatal).
    """
    norm = normalize(word)
    if norm in vocab:
        return norm
    candidates = get_close_matches(norm, vocab.keys(), n=1, cutoff=cutoff)
    return candidates[0] if candidates else None

# ---------------------------------------------------------------------
# 1) Real Nepali number words -> int
# ---------------------------------------------------------------------

NEPALI_UNITS = {
    "शून्य": 0, "एक": 1, "दुई": 2, "तीन": 3, "चार": 4, "पाँच": 5,
    "छ": 6, "सात": 7, "आठ": 8, "नौ": 9, "दश": 10,
    "एघार": 11, "बाह्र": 12, "तेह्र": 13, "चौध": 14, "पन्ध्र": 15,
    "सोह्र": 16, "सत्र": 17, "अठार": 18, "उन्नाइस": 19,
    "बीस": 20, "एक्काइस": 21, "बाइस": 22, "तेइस": 23, "चौबीस": 24,
    "पच्चीस": 25, "छब्बीस": 26, "सत्ताइस": 27, "अठ्ठाइस": 28, "उनन्तीस": 29,
    "तीस": 30, "एकतीस": 31, "बत्तीस": 32, "तेत्तीस": 33, "चौँतीस": 34,
    "पैँतीस": 35, "छत्तीस": 36, "सैँतीस": 37, "अठतीस": 38, "उनन्चालीस": 39,
    "चालीस": 40, "एकचालीस": 41, "बयालीस": 42, "त्रिचालीस": 43,
    "चौरालीस": 44, "पैँतालीस": 45, "छयालीस": 46, "सतचालीस": 47,
    "अठचालीस": 48, "उनन्पचास": 49,
    "पचास": 50, "एकाउन्न": 51, "बाउन्न": 52, "त्रिपन्न": 53, "चवन्न": 54,
    "पचपन्न": 55, "छपन्न": 56, "सन्ताउन्न": 57, "अन्ठाउन्न": 58, "उनान्साठी": 59,
    "साठी": 60, "एकसठ्ठी": 61, "बयसठ्ठी": 62, "त्रिसठ्ठी": 63, "चौंसठ्ठी": 64,
    "पैंसठ्ठी": 65, "छैंसठ्ठी": 66, "सतसठ्ठी": 67, "अठसठ्ठी": 68, "उनन्सत्तरी": 69,
    "सत्तरी": 70, "एकहत्तर": 71, "बहत्तर": 72, "त्रिहत्तर": 73, "चौहत्तर": 74,
    "पचहत्तर": 75, "छयहत्तर": 76, "सतहत्तर": 77, "अठहत्तर": 78, "उनासी": 79,
    "असी": 80, "एकासी": 81, "बयासी": 82, "त्रियासी": 83, "चौरासी": 84,
    "पचासी": 85, "छयासी": 86, "सतासी": 87, "अठासी": 88, "उनान्नब्बे": 89,
    "नब्बे": 90, "एकानब्बे": 91, "बयानब्बे": 92, "त्रियानब्बे": 93, "चौरानब्बे": 94,
    "पन्चानब्बे": 95, "छयानब्बे": 96, "सन्तानब्बे": 97, "अन्ठानब्बे": 98, "उनान्सय": 99,
}

# multiplier words (Nepali uses lakh/crore grouping, not thousand/million)
NEPALI_MULTIPLIERS = {
    "सय": 100,
    "हजार": 1_000,
    "लाख": 100_000,
    "करोड": 10_000_000,
    "अर्ब": 1_000_000_000,
    "खर्ब": 100_000_000_000,
}


def parse_nepali_words(text: str, strict: bool = False) -> int:
    """'चार हजार चार सय चौरालीस' -> 4444

    strict=False (default): unrecognized/misspelled tokens are resolved
    via fuzzy matching against the known vocabulary when possible.
    strict=True: any unmatched token raises immediately (no guessing).
    """
    words = text.strip().split()
    total = 0
    current = 0
    for w in words:
        key = closest_match(w, NEPALI_UNITS) or closest_match(w, NEPALI_MULTIPLIERS)
        if key in NEPALI_UNITS:
            current += NEPALI_UNITS[key]
        elif key in NEPALI_MULTIPLIERS:
            mult = NEPALI_MULTIPLIERS[key]
            if mult == 100:
                current = (current or 1) * mult
            else:
                total += (current or 1) * mult
                current = 0
        elif strict:
            raise ValueError(f"Unrecognized Nepali number word: {w!r}")
        else:
            raise ValueError(
                f"Unrecognized Nepali number word: {w!r} "
                f"(no close match found even fuzzily)"
            )
    return total + current


# ---------------------------------------------------------------------
# 2) English number words spelled phonetically in Devanagari -> int
# ---------------------------------------------------------------------

PHONETIC_UNITS = {
    "जिरो": 0, "वान": 1, "वन": 1, "टु": 2, "थ्री": 3, "फोर": 4, "फाइभ": 5,
    "सिक्स": 6, "सेभेन": 7, "एट": 8, "नाइन": 9, "टेन": 10,
    "इलेभेन": 11, "ट्वेल्भ": 12, "थर्टीन": 13, "फोर्टिन": 14, "फिफ्टिन": 15,
    "सिक्सटिन": 16, "सेभेन्टिन": 17, "एटिन": 18, "नाइन्टिन": 19,
    "ट्वान्टी": 20, "थर्टी": 30, "फोर्टी": 40, "फिफ्टी": 50,
    "सिक्स्टी": 60, "सेभेन्टी": 70, "एटी": 80, "नाइन्टी": 90,
}

PHONETIC_MULTIPLIERS = {
    "हन्ड्रेड": 100,
    "थाउजन्ड": 1_000,
    "थाउजैंड": 1_000,   # common alt. spelling, too different for fuzzy cutoff to catch
    "मिलियन": 1_000_000,
    "बिलियन": 1_000_000_000,
}


def parse_phonetic_english(text: str) -> int:
    """'फोर थाउजन्ड फोर हन्ड्रेड फोर्टी फोर' -> 4444

    Tolerates common transliteration variance (फोर/फ़ोर, वान/वन,
    थाउजन्ड/थाउजैंड, etc.) via fuzzy matching.
    """
    words = text.strip().split()
    total = 0
    current = 0
    for w in words:
        key = closest_match(w, PHONETIC_UNITS) or closest_match(w, PHONETIC_MULTIPLIERS)
        if key in PHONETIC_UNITS:
            current += PHONETIC_UNITS[key]
        elif key in PHONETIC_MULTIPLIERS:
            mult = PHONETIC_MULTIPLIERS[key]
            if mult == 100:
                current = (current or 1) * mult
            else:
                total += (current or 1) * mult
                current = 0
        else:
            raise ValueError(f"Unrecognized phonetic word: {w!r}")
    return total + current


if __name__ == "__main__":
    a = "चार हजार चार सय चौरालीस"
    b = "फोर थाउजन्ड फोर हन्ड्रेड फोर्टी फोर"
    print(a, "->", parse_nepali_words(a))
    print(b, "->", parse_phonetic_english(b))

    # Same numbers, with realistic spelling/pronunciation noise
    a_noisy = "चार हजार चार सय चौरालिस"       # चौरालीस -> चौरालिस (short ी)
    b_noisy = "फ़ोर थाउजैंड फ़ोर हन्ड्रेड फोर्टी फ़ोर"  # nuqta + थाउजैंड variant
    print(a_noisy, "->", parse_nepali_words(a_noisy))
    print(b_noisy, "->", parse_phonetic_english(b_noisy))