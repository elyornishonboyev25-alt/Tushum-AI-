"""Conservative comparison of two listeners; never rewrites a caller's words.

These rules detect disagreements, not confidence or intent. Missing or ambiguous
evidence is a reason to clarify, never a reason to infer money from the ledger.
"""

import re
from decimal import Decimal
from difflib import SequenceMatcher

NUMBER_WORDS = {
    "nol": 0,
    "bir": 1,
    "ikki": 2,
    "uch": 3,
    "tort": 4,
    "besh": 5,
    "olti": 6,
    "yetti": 7,
    "sakkiz": 8,
    "toqqiz": 9,
    "on": 10,
    "yigirma": 20,
    "ottiz": 30,
    "qirq": 40,
    "ellik": 50,
    "oltmish": 60,
    "yetmish": 70,
    "sakson": 80,
    "toqson": 90,
    "yarim": Decimal("0.5"),
    "ноль": 0,
    "один": 1,
    "одна": 1,
    "одно": 1,
    "два": 2,
    "две": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
    "десять": 10,
    "одиннадцать": 11,
    "двенадцать": 12,
    "тринадцать": 13,
    "четырнадцать": 14,
    "пятнадцать": 15,
    "шестнадцать": 16,
    "семнадцать": 17,
    "восемнадцать": 18,
    "девятнадцать": 19,
    "двадцать": 20,
    "тридцать": 30,
    "сорок": 40,
    "пятьдесят": 50,
    "шестьдесят": 60,
    "семьдесят": 70,
    "восемьдесят": 80,
    "девяносто": 90,
    "сто": 100,
    "двести": 200,
    "триста": 300,
    "четыреста": 400,
    "пятьсот": 500,
    "шестьсот": 600,
    "семьсот": 700,
    "восемьсот": 800,
    "девятьсот": 900,
    "полтора": Decimal("1.5"),
    "полторы": Decimal("1.5"),
    "полмиллиона": 500000,
}
SCALES = {
    "yuz": 100,
    "ming": 1000,
    "million": 1000000,
    "mln": 1000000,
    "milliard": 1000000000,
    "тысяча": 1000,
    "тысячи": 1000,
    "тысяч": 1000,
    "тысячу": 1000,
    "тыс": 1000,
    "миллион": 1000000,
    "миллиона": 1000000,
    "миллионов": 1000000,
    "млн": 1000000,
    "миллиард": 1000000000,
}


def normalized(text):
    text = text.casefold().replace("ё", "е")
    text = re.sub(r"['‘’ʻʼ`´]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def latinized(text):
    alphabet = dict(
        zip(
            "абвгдеёжзийклмнопрстуфхцчшщъыьэюяўқғҳ",
            (
                "a",
                "b",
                "v",
                "g",
                "d",
                "e",
                "yo",
                "j",
                "z",
                "i",
                "y",
                "k",
                "l",
                "m",
                "n",
                "o",
                "p",
                "r",
                "s",
                "t",
                "u",
                "f",
                "x",
                "ts",
                "ch",
                "sh",
                "shch",
                "",
                "i",
                "",
                "e",
                "yu",
                "ya",
                "o",
                "q",
                "g",
                "h",
            ),
            strict=True,
        )
    )
    return "".join(alphabet.get(char, char) for char in text)


def tokens(text):
    text = normalized(text)
    # Grouped digits are one number; decimal fractions stay fractions.
    text = re.sub(
        r"\d{1,3}(?:[ .\u00a0,]\d{3})+(?!\d)",
        lambda m: re.sub(r"[ .\u00a0,]", "", m[0]),
        text,
    )
    return re.findall(r"\d+(?:[.,]\d+)?|[^\W\d_]+", text)


def number_values(text):
    result = []
    total = Decimal(0)
    group = Decimal(0)
    active = False
    for word in tokens(text) + [""]:
        if word not in NUMBER_WORDS and word not in SCALES:
            word = latinized(word)
        # Spoken Uzbek dates/counts may carry a grammatical ending. Only remove
        # an ending when the remainder is an actual number, never from names.
        if word not in NUMBER_WORDS and word not in SCALES:
            for ending in (
                "inchi",
                "nchi",
                "tadan",
                "taga",
                "tani",
                "ta",
                "dan",
                "ga",
                "ni",
            ):
                stem = word.removesuffix(ending)
                if stem != word and (stem in NUMBER_WORDS or stem in SCALES):
                    word = stem
                    break
        if word in NUMBER_WORDS or re.fullmatch(r"\d+(?:[.,]\d+)?", word):
            value = NUMBER_WORDS.get(word)
            group += (
                Decimal(str(value))
                if value is not None
                else Decimal(word.replace(",", "."))
            )
            active = True
        elif word in SCALES:
            scale = SCALES[word]
            if scale == 100:
                group = (group or 1) * scale
            else:
                total += (group or 1) * scale
                group = Decimal(0)
            active = True
        elif active:
            result.append(total + group)
            total = group = Decimal(0)
            active = False
    return result


def explicit_payment_values(text, balance):
    """Conservative proposal check; never multiplies an ambiguous 'ikki yuz'."""
    words = normalized(text)
    if re.search(r"\b(?:emas|эмас)\b", words):
        words = re.split(r"\b(?:emas|эмас)\b", words)[-1]
    elif re.search(r"\bне\b.*[,;]\s*а\b", words):
        words = re.split(r"[,;]\s*а\b", words)[-1]
    currency = bool(re.search(r"\b(som|сум|сумов|сўм)\b", words))
    values = {
        value
        for value in number_values(words)
        if value >= 1000 or currency and value > 0
    }
    if re.search(
        r"\b(yarmini|yarmi|половину|половина)\b", words + " " + latinized(words)
    ):
        values.add(Decimal(balance) / 2)
    if re.search(
        r"\b(hammasini|hammasi|toliq|полностью|всю)\b", words + " " + latinized(words)
    ):
        values.add(Decimal(balance))
    return values


def negative(text):
    words = normalized(text)
    words += " " + latinized(words)
    return bool(
        re.search(
            r"\b(yoq|emas|нет|не|никогда|отказываюсь)\b|"
            r"\b(?:tolamay|bermay|olmay|kelishmad|aytmad|tasdiqlamay)\w*|"
            r"\b\w*(?:mayman|maymiz|maydi|miman|madim|maganman|olmay)\w*\b",
            words,
        )
    )


def tentative(text):
    words = normalized(text)
    return bool(
        re.search(
            r"\b(balki|agar|urinaman|ehtimol|bolsa|если|постараюсь|возможно|наверное)\b|harakat qil",
            words + " " + latinized(words),
        )
    )


def date_cues(text):
    words = normalized(text)
    words += " " + latinized(words)
    cues = set()
    for name, pattern in {
        "tomorrow": r"\bertaga\b|\bзавтра\b",
        "today": r"\bbugun\b|\bсегодня\b",
        "after_tomorrow": r"\bindin(?:ga)?\b|\bпослезавтра\b",
        "afternoon": r"tushdan keyin|после обеда",
        "evening": r"\bkechqurun\b|\bвечером\b",
        "minutes": r"\bdaqiqa\w*|\bминут\w*",
        "hours": r"\bsoat\w*|\bчас\w*",
        "monday": r"\bdushanba\b|понедельник",
        "tuesday": r"\bseshanba\b|вторник",
        "wednesday": r"\bchorshanba\b|среду|среда",
        "thursday": r"\bpayshanba\b|четверг",
        "friday": r"\bjuma\b|пятницу|пятница",
        "saturday": r"\bshanba\b|субботу|суббота",
        "sunday": r"\byakshanba\b|воскресенье",
    }.items():
        if re.search(pattern, words):
            cues.add(name)
    return cues


def unexpected_script(text):
    # Kazakh and other Cyrillic-specific letters are not Uzbek/Russian output.
    # Uzbek Cyrillic ў, қ, ғ, ҳ remains valid caller speech.
    return bool(re.search(r"[әіңұүөһіїєґ]", text.casefold()))


def word_similarity(first, second):
    left = latinized(" ".join(tokens(first))).split()
    right = latinized(" ".join(tokens(second))).split()
    return SequenceMatcher(None, left, right, autojunk=False).ratio()


def agreement(first, second):
    if not first.strip() or not second.strip():
        return False
    if max(len(first), len(second)) <= 50 and ("?" in first) != ("?" in second):
        return False
    if number_values(first) != number_values(second):
        return False
    if negative(first) != negative(second) or tentative(first) != tentative(second):
        return False
    if date_cues(first) != date_cues(second):
        return False
    if unexpected_script(first) or unexpected_script(second):
        return False
    # Punctuation and number formatting do not make two different statements.
    left, right = (
        latinized(" ".join(tokens(first))),
        latinized(" ".join(tokens(second))),
    )
    return SequenceMatcher(None, left, right, autojunk=False).ratio() >= 0.55
