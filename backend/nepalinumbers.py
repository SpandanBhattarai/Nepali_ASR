import unicodedata

DROP_NON_NUMBERS =True
USE_NEPALI_DIGITS = True   # True -> १२५३ , False -> 1253
_TO_DEVANAGARI = str.maketrans("0123456789", "०१२३४५६७८९")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = s.replace("\u0901", "\u0902")   # chandrabindu -> anusvara, so पाँच == पांच
    s = s.replace("\u0940", "\u093F")   # ी -> ि   (तीन == तिन)
    s = s.replace("\u0942", "\u0941")   # ू -> ु
    s = s.replace("\u0908","\u0907")
    s = s.replace("\u090A","\u0909")
    return s

_UNITS = {
    "शून्य": 0, "सुन्ना": 0,
    "एक": 1, "दुई": 2, "तीन": 3, "चार": 4, "पाँच": 5, "छ": 6, "सात": 7, "आठ": 8, "नौ": 9,
    "दश": 10, "दस": 10, "एघार": 11, "बाह्र": 12, "तेह्र": 13, "चौध": 14, "पन्ध्र": 15,
    "सोह्र": 16, "सत्र": 17, "अठार": 18, "उन्नाइस": 19,
    "बीस": 20, "एक्काइस": 21, "बाइस": 22, "तेइस": 23, "चौबीस": 24, "पच्चीस": 25,
    "छब्बीस": 26, "सत्ताइस": 27, "अठ्ठाइस": 28, "उनन्तिस": 29,
    "तीस": 30, "एकतीस": 31, "बत्तीस": 32, "तेत्तीस": 33, "चौँतीस": 34, "पैँतीस": 35,
    "छत्तीस": 36, "सैँतीस": 37, "अठतीस": 38, "उनन्चालीस": 39,
    "चालीस": 40, "एकचालीस": 41, "बयालीस": 42, "त्रिचालीस": 43, "चौवालीस": 44,
    "पैंतालीस": 45, "छयालीस": 46, "सत्चालीस": 47, "अठचालीस": 48, "उनन्चास": 49,
    "पचास": 50, "एकाउन्न": 51, "बाउन्न": 52, "त्रिपन्न": 53, "चौवन्न": 54, "पचपन्न": 55,
    "छपन्न": 56, "सन्ताउन्न": 57, "अन्ठाउन्न": 58, "उनान्साठी": 59,
    "साठी": 60, "एकसट्ठी": 61, "बैसट्ठी": 62, "त्रिसट्ठी": 63, "चौसट्ठी": 64,
    "पैसट्ठी": 65, "छयसट्ठी": 66, "सतसट्ठी": 67, "अठसट्ठी": 68, "उनन्सत्तरी": 69,
    "सत्तरी": 70, "एकहत्तर": 71, "बहत्तर": 72, "त्रिहत्तर": 73, "चौहत्तर": 74,
    "पचहत्तर": 75, "छयहत्तर": 76, "सतहत्तर": 77, "अठहत्तर": 78, "उनासी": 79,
    "असी": 80, "एकासी": 81, "बयासी": 82, "त्रियासी": 83, "चौरासी": 84, "पचासी": 85,
    "छयासी": 86, "सतासी": 87, "अठासी": 88, "उनान्नब्बे": 89,
    "नब्बे": 90, "एकान्नब्बे": 91, "बयान्नब्बे": 92, "त्रियान्नब्बे": 93,
    "चौरान्नब्बे": 94, "पन्चानब्बे": 95, "छयान्नब्बे": 96, "सन्तान्नब्बे": 97,
    "अन्ठान्नब्बे": 98, "उनान्सय": 99,
    # common alternate spellings; add any variant you see in the raw ASR output
    "पचीस": 25, "छब्बिस": 26, "पैतीस": 35, "चौतीस": 34, "सैतीस": 37,
    "दो": 2, "छह": 6, "छः": 6, "नव": 9,
    "सठ": 60, "सठी": 60, "साठ": 60, "साठि": 60,
    "बीसौं": 20, "उन्नाईस": 19, "अठाइस": 28, "पैंसठ्ठी": 65, "सत्ताउन्न": 57,
    "उनानब्बे":89, "उननान्साई":99, "उनासय":99, "उननासी": 99, "छैसठी":66,
    "बासठी":62, "बासठ्ठी":62, "उननान्सय": 99, "उननासय":99
}
_SCALES = {"सय": 100, "सी": 100, "स": 100, "से": 100, "सै": 100, "सौ": 100, "हज़ार": 1000, "हजार": 1000, "लाख": 100000, "करोड": 10000000, "अर्ब": 1000000000}

VOCAB = {_norm(k): v for k, v in {**_UNITS, **_SCALES}.items()}
SCALE_WORDS = {_norm(k) for k in _SCALES}
AMBIGUOUS = set()
_MAXLEN = max(len(k) for k in VOCAB)


def _segment(token):
    if not token:
        return None
    n = len(token)
    best = [None] * (n + 1)
    best[0] = []
    for i in range(1, n + 1):
        for j in range(max(0, i - _MAXLEN), i):
            if best[j] is not None and token[j:i] in VOCAB:
                cand = best[j] + [token[j:i]]
                if best[i] is None or len(cand) < len(best[i]):
                    best[i] = cand
    return best[n]


def _convert_run(words):
    numbers = []
    total = chunk = 0
    started = prev_scale = False
    prev_v = None
    for w in words:
        v = VOCAB[w]
        if w in SCALE_WORDS:
            if v == 100:
                chunk = (chunk or 1) * 100
            else:
                total += (chunk or 1) * v
                chunk = 0
            prev_scale = True
        else:
            is_tens = 20 <= v < 100 and v % 10 == 0
            glued_prefix = is_tens and prev_v is not None and 1 <= prev_v <= 9   # "दो सठी" -> 62
            if started and not prev_scale and not glued_prefix:
                numbers.append(total + chunk)   # new separate number (e.g. digit-by-digit)
                total = chunk = 0
            chunk += v
            prev_scale = False
        prev_v = None if w in SCALE_WORDS else v
        started = True
    numbers.append(total + chunk)

    out = str(numbers[0])
    for prev, cur in zip(numbers, numbers[1:]):
        # glue single digits together (phone numbers), otherwise keep a space
        out += str(cur) if (prev < 10 and cur < 10) else " " + str(cur)
    return out


def normalize_nepali_numbers(text: str) -> str:
    tokens = _norm(text).split()
    segs = [_segment(t) for t in tokens]
    has_other_words = any(s is None for s in segs)

    out, run = [], []

    def flush():
        if not run:
            return
        if len(run) == 1 and run[0] in AMBIGUOUS and has_other_words:
            out.append(run[0])             
        else:
            out.append(_convert_run(run))
        run.clear()

    for tok, seg in zip(tokens, segs):
        if seg:
            run.extend(seg)
        else:
            flush()
    flush()

    result = " ".join(out)
    return result.translate(_TO_DEVANAGARI) if USE_NEPALI_DIGITS else result