"""Линтер утечек teaser: чистая функция без фреймворков и внешних зависимостей.

Проверяет переданные поля teaser-карточки на наличие сведений, которые не должны
попадать в публичный обезличенный текст: имя организации, URL, e-mail, телефон,
регистрационные номера (ИНН/ОГРН/VAT). Найденные фрагменты нигде не печатаются
и не логируются — в нарушение кладётся только код и имя поля.
"""

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

# Минимальная длина «отличительного» слова имени организации.
_MIN_DISTINCTIVE_WORD_LEN = 4
# Минимальная длина слова, при которой допускается вхождение внутри токена.
_MIN_EMBED_WORD_LEN = 7
# Минимальное число подряд идущих однобуквенных токенов для склейки.
_MIN_SINGLE_LETTER_RUN = 3
# Максимальное число соседних токенов, склеиваемых при сравнении.
_MAX_GLUE_TOKENS = 3
# Минимальная длина метки домена (чтобы «т.е.», «и.т.д.» не срабатывали).
_MIN_DOMAIN_LABEL_LEN = 2
# Минимальная длина TLD.
_MIN_TLD_LEN = 2
# Минимальное число цифр в телефонном номере без «+».
_MIN_PHONE_DIGITS = 9
# Минимальное число цифр в телефонном номере с «+».
_MIN_PHONE_DIGITS_WITH_PLUS = 7
# Допустимые длины непрерывных последовательностей цифр (ИНН/ОГРН).
_REGISTRY_ID_LENGTHS = frozenset({10, 12, 13, 15})
# Минимальное число цифр в VAT-номере после буквенного кода.
_MIN_VAT_DIGITS = 8
# Максимальное число цифр в VAT-номере после буквенного кода.
_MAX_VAT_DIGITS = 12
# Максимальная длина значения поля, после которой find_leaks бросает ValueError.
_MAX_FIELD_LEN = 4096
# Длина окна слева от «@» при поиске e-mail.
_EMAIL_LOCAL_WINDOW = 64
# Длина окна справа от «@» при поиске e-mail.
_EMAIL_DOMAIN_WINDOW = 253

# Слова юридической формы, отбрасываемые при сравнении имени (после транслитерации).
_LEGAL_FORM_WORDS = frozenset(
    {
        "gmbh",
        "ag",
        "llc",
        "ltd",
        "inc",
        "sa",
        "bv",
        "oy",
        "ab",
        "oao",
        "ooo",
        "zao",
        "ao",
        "pao",
        "ip",
        "kg",
        "co",
        "corp",
        "spa",
        "srl",
        "sarl",
        "plc",
    }
)

# Таблица транслитерации кириллицы в латиницу (строчные буквы).
_CYRILLIC_TO_LATIN = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "i",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "kh",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shch",
        "ъ": "",
        "ь": "",
        "ы": "y",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
)

# Таблица гомоглифов: часто путаемые греческие буквы → латиница (по внешнему сходству).
_GREEK_HOMOGLYPHS = str.maketrans(
    {
        "ο": "o",
        "Ο": "O",
        "α": "a",
        "ε": "e",
        "ρ": "p",
        "ν": "v",
        "τ": "t",
        "κ": "k",
        "ι": "i",
        "υ": "u",
        "χ": "x",
        "β": "b",
        "η": "h",
        "μ": "m",
    }
)

# Таблица визуальных гомоглифов: кириллица → латиница по внешнему сходству.
# Применяется после casefold, поэтому заглавные буквы уже стали строчными.
_VISUAL_HOMOGLYPHS = str.maketrans(
    {
        "а": "a",
        "е": "e",
        "ё": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "у": "y",
        "х": "x",
        "і": "i",
        "ј": "j",
        "ѕ": "s",
        "ԁ": "d",
        "ԛ": "q",
        "ԝ": "w",
        "в": "b",
        "н": "h",
        "к": "k",
        "м": "m",
        "т": "t",
        "ь": "b",
    }
)

# Всё, кроме латинских букв и цифр, заменяется на пробел.
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
# Пробелы схлопываются в один.
_MULTISPACE_RE = re.compile(r"\s+")

# URL: http://, https://, www. или домен вида метка.tld (искать в тексте БЕЗ casefold).
# TLD: латинские буквы любого регистра, кириллица только строчными («работает.Она» — не домен) или punycode xn--.
_LABEL_CHARS = "a-zA-Zа-яА-ЯёЁ0-9-"
_URL_RE = re.compile(
    r"(?i:https?://|www\.)|"
    rf"(?<![{_LABEL_CHARS}])[{_LABEL_CHARS}]{{{_MIN_DOMAIN_LABEL_LEN},}}\."
    rf"(?:[a-zA-Z]{{{_MIN_TLD_LEN},}}|[а-яё]{{{_MIN_TLD_LEN},}}|xn--[a-zA-Z0-9-]+)(?![{_LABEL_CHARS}])"
)
# E-mail: локальная_часть@домен.tld (по исходному casefold-тексту).
_EMAIL_RE = re.compile(rf"[^\s@]+@[^\s@]+\.(?:[a-zа-яё]{{{_MIN_TLD_LEN},}}|xn--[a-z0-9-]+)")
# Непрерывная последовательность цифр (ИНН/ОГРН) с границами «не-цифра».
_DIGIT_RUN_RE = re.compile(r"(?<!\d)\d+(?!\d)")
# VAT-подобное: две латинские буквы + 8–12 цифр (допустим один пробел между).
_VAT_RE = re.compile(rf"(?<![a-z0-9])[a-z]{{2}} ?\d{{{_MIN_VAT_DIGITS},{_MAX_VAT_DIGITS}}}(?!\d)")
# Телефон: необязательный «+», цифры с разделителями (пробел, дефис, точка, скобки).
_PHONE_RE = re.compile(r"\+?[\d][\d\s().-]{6,}")

# Дефисы и тире, приводимые к «-».
_DASHES = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"
# Защитные замены «дефангов»: «[.]», «(.)», «{.}» (с любыми пробелами вокруг) и голая « . » → «.».
_DEFANG_RE = re.compile(r"\s*(?:\[\.\]|\(\.\)|\{\.\})\s*| \. ")

# Общие (неотличительные) слова имени организации — исходные формы.
_GENERIC_ORG_WORDS_RAW = frozenset(
    {
        "logistik",
        "logistics",
        "logistic",
        "логистика",
        "trade",
        "трейд",
        "group",
        "групп",
        "группа",
        "holding",
        "холдинг",
        "invest",
        "инвест",
        "capital",
        "капитал",
        "bank",
        "банк",
        "systems",
        "системс",
        "solutions",
        "services",
        "сервис",
        "consulting",
        "консалтинг",
        "development",
        "девелопмент",
        "energy",
        "энерджи",
        "partners",
        "партнёрс",
        "international",
        "интернешнл",
        "global",
        "euro",
        "industries",
    }
)

# Свёртка фонетических/визуальных ключей: замены по порядку, затем схлопывание дублей.
_FOLD_REPLACEMENTS = (
    ("kh", "h"),
    ("ch", "h"),
    ("ck", "k"),
    ("c", "k"),
    ("q", "k"),
    ("ph", "f"),
    ("w", "v"),
    ("x", "ks"),
    ("y", "i"),
    ("j", "i"),
)


def _fold(text: str) -> str:
    """Свёртка ключа: фонетические замены и схлопывание двойных одинаковых букв."""
    for old, new in _FOLD_REPLACEMENTS:
        text = text.replace(old, new)
    # Двойные одинаковые буквы → одна.
    return re.sub(r"([a-z0-9])\1+", r"\1", text)


def _glue_single_letter_tokens(tokens: list[str]) -> list[str]:
    """Склеивает подряд идущие однобуквенные токены (≥ 3) в один токен."""
    result: list[str] = []
    run: list[str] = []
    for token in tokens:
        if len(token) == 1:
            run.append(token)
        else:
            if len(run) >= _MIN_SINGLE_LETTER_RUN:
                result.append("".join(run))
            else:
                result.extend(run)
            run = []
            result.append(token)
    if len(run) >= _MIN_SINGLE_LETTER_RUN:
        result.append("".join(run))
    else:
        result.extend(run)
    return result


def _phonetic_key(text: str) -> list[str]:
    """Фонетический ключ: casefold, транслитерация RU→EN, склейка однобуквенных токенов, свёртка."""
    prepared = _prepare(text).casefold()
    transliterated = prepared.translate(_CYRILLIC_TO_LATIN)
    tokens = _NON_ALNUM_RE.split(transliterated)
    tokens = _glue_single_letter_tokens(tokens)
    return [_fold(token) for token in tokens]


def _visual_key(text: str) -> list[str]:
    """Визуальный ключ: casefold, гомоглифы кириллицы, транслитерация остатка, склейка, свёртка."""
    prepared = _prepare(text).casefold()
    homoglyphed = prepared.translate(_VISUAL_HOMOGLYPHS)
    transliterated = homoglyphed.translate(_CYRILLIC_TO_LATIN)
    tokens = _NON_ALNUM_RE.split(transliterated)
    tokens = _glue_single_letter_tokens(tokens)
    return [_fold(token) for token in tokens]


class LeakKind(StrEnum):
    """Виды утечек, обнаруживаемых линтером."""

    ORG_NAME_IN_TEASER = "org_name_in_teaser"
    URL_IN_TEASER = "url_in_teaser"
    EMAIL_IN_TEASER = "email_in_teaser"
    PHONE_IN_TEASER = "phone_in_teaser"
    REGISTRY_ID_IN_TEASER = "registry_id_in_teaser"


@dataclass(frozen=True)
class LeakViolation:
    """Одно нарушение: код вида утечки и имя поля, где оно найдено."""

    code: LeakKind
    field: str


def _prepare(text: str) -> str:
    """Единый шаг предобработки перед всеми проверками.

    Приводит полноширинные символы к ASCII, удаляет zero-width и combining-марки,
    переводит цифры любой системы в ASCII, нормализует дефисы, снимает диакритику
    и заменяет часто путаемые греческие буквы на латиницу.
    """
    text = unicodedata.normalize("NFKC", text)
    # Удалить символы категории Cf (zero-width, мягкий перенос и т.п.).
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    # Цифры любой системы (категория Nd) → ASCII.
    text = "".join(str(unicodedata.digit(ch)) if unicodedata.category(ch) == "Nd" else ch for ch in text)
    # Дефисы и тире → «-».
    text = text.translate(str.maketrans(_DASHES, "-" * len(_DASHES)))
    # Снять диакритику: NFKD + удаление combining-марок, затем NFC.
    decomposed = "".join(ch for ch in unicodedata.normalize("NFKD", text) if unicodedata.category(ch) != "Mn")
    text = unicodedata.normalize("NFC", decomposed)
    # Гомоглифы греческих букв → латиница.
    text = text.translate(_GREEK_HOMOGLYPHS)
    # Защитные замены «дефангов».
    text = _DEFANG_RE.sub(".", text)
    return text


# Общие слова имени, прогоняемые через оба ключа при импорте модуля.
_GENERIC_ORG_WORDS = frozenset(
    token for word in _GENERIC_ORG_WORDS_RAW for token in (*_phonetic_key(word), *_visual_key(word))
)


def _normalize(text: str) -> str:
    """Приводит текст к сравнимому виду: NFKC, casefold, транслитерация, только [a-z0-9] и пробелы."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    transliterated = normalized.translate(_CYRILLIC_TO_LATIN)
    cleaned = _NON_ALNUM_RE.sub(" ", transliterated)
    return _MULTISPACE_RE.sub(" ", cleaned).strip()


def _match_word(tokens: list[str], word: str) -> bool:
    """Проверяет, срабатывает ли отличительное слово word на токенах текста."""
    for token in tokens:
        if token == word or token.startswith(word):
            return True
        if len(word) >= _MIN_EMBED_WORD_LEN and word in token:
            return True
    # Склейка 2–3 соседних токенов, равная word или начинающаяся с word.
    for size in range(2, _MAX_GLUE_TOKENS + 1):
        for i in range(len(tokens) - size + 1):
            glued = "".join(tokens[i : i + size])
            if glued == word or glued.startswith(word):
                return True
    return False


def _match_short_name(tokens: list[str], name: str) -> bool:
    """Короткое имя: точное совпадение токена или склейки 2–3 соседних токенов («N L», «N-L», «N.L.»)."""
    for size in range(1, _MAX_GLUE_TOKENS + 1):
        for i in range(len(tokens) - size + 1):
            if "".join(tokens[i : i + size]) == name:
                return True
    return False


def _match_full_name(tokens: list[str], name_tokens: list[str]) -> bool:
    """Проверяет полное имя как подряд идущую последовательность токенов или склейку 1–3 токенов."""
    if not name_tokens:
        return False
    name = "".join(name_tokens)
    # Подряд идущая последовательность токенов текста.
    for i in range(len(tokens) - len(name_tokens) + 1):
        if tokens[i : i + len(name_tokens)] == name_tokens:
            return True
    # Склеенная форма: склейка 1–3 соседних токенов текста.
    for size in range(1, _MAX_GLUE_TOKENS + 1):
        for i in range(len(tokens) - size + 1):
            if "".join(tokens[i : i + size]) == name:
                return True
    return False


def _find_org_name(field_text: str, org_name: str, org_aliases: Sequence[str]) -> bool:
    """Проверяет, встречается ли имя организации (или алиас) в тексте поля.

    Сравнение идёт по словам для двух ключей (фонетического и визуального),
    нарушение — при совпадении любого из них.
    """
    text_p = _phonetic_key(field_text)
    text_v = _visual_key(field_text)

    for index, name in enumerate((org_name, *org_aliases)):
        if not name:
            continue
        is_alias = index > 0
        for key_fn, text_tokens in ((_phonetic_key, text_p), (_visual_key, text_v)):
            name_tokens = key_fn(name)
            if not name_tokens:
                continue
            # Юридическую форму убираем только из официального имени: алиас («AB», «CO») — это и есть искомое имя.
            if not is_alias:
                name_tokens = [t for t in name_tokens if t not in _LEGAL_FORM_WORDS]
            if not name_tokens:
                continue
            distinctive = [
                t for t in name_tokens if t not in _GENERIC_ORG_WORDS and len(t) >= _MIN_DISTINCTIVE_WORD_LEN
            ]
            name_joined = "".join(name_tokens)

            if distinctive:
                if any(_match_word(text_tokens, w) for w in distinctive):
                    return True
                if _match_full_name(text_tokens, name_tokens):
                    return True
            elif len(name_joined) < _MIN_DISTINCTIVE_WORD_LEN:
                # Имя короче 4 символов и без отличительных слов — только точное совпадение токена.
                if _match_short_name(text_tokens, name_joined):
                    return True
            else:
                # Только общие слова — срабатывает лишь полное имя.
                if _match_full_name(text_tokens, name_tokens):
                    return True

    return False


def _find_url(field_text: str) -> bool:
    """Проверяет наличие URL-подобных подстрок (регистр сохраняется: важен для кириллического TLD)."""
    return bool(_URL_RE.search(field_text))


def _find_email(field_text: str) -> bool:
    """Проверяет наличие e-mail, схлопывая пробелы вокруг «@» и точек в домене.

    Если «@» нет — сразу False; иначе ищет только в окне вокруг каждого «@».
    """
    text = field_text.casefold()
    if "@" not in text:
        return False
    # Схлопнуть пробелы вокруг «@» и вокруг точек в домене.
    text = re.sub(r"\s*@\s*", "@", text)
    text = re.sub(r"\s*\.\s*", ".", text)
    for match in re.finditer("@", text):
        start = max(0, match.start() - _EMAIL_LOCAL_WINDOW)
        end = min(len(text), match.end() + _EMAIL_DOMAIN_WINDOW)
        if _EMAIL_RE.search(text, start, end):
            return True
    return False


def _find_registry_id(field_text: str) -> bool:
    """Проверяет наличие ИНН/ОГРН (10/12/13/15 цифр) или VAT-номера."""
    normalized = _normalize(field_text)
    for match in _DIGIT_RUN_RE.finditer(normalized):
        if len(match.group()) in _REGISTRY_ID_LENGTHS:
            return True
    return bool(_VAT_RE.search(normalized))


# Дата: dd.mm.yyyy, dd/mm/yyyy, dd.mm.yy, yyyy-mm-dd; день 1–31, месяц 1–12, год 1900–2099.
_DATE_RE = re.compile(
    r"(?<!\d)"
    r"(?:"
    r"(?:0[1-9]|[12]\d|3[01])[./](?:0[1-9]|1[0-2])[./](?:\d{2}|(?:19|20)\d{2})"
    r"|"
    r"(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])"
    r")"
    r"(?!\d)"
)
# Символ вне класса [\d\s().-], которым маскируются даты.
_DATE_MASK_CHAR = "\u00b6"


def _mask_dates(text: str) -> str:
    """Заменяет валидные даты на символ вне класса [\\d\\s().-], разрывая цепочку цифр."""
    return _DATE_RE.sub(_DATE_MASK_CHAR, text)


def _find_phone(field_text: str) -> bool:
    """Проверяет наличие телефонного номера (с разделителями или с «+»)."""
    text = _mask_dates(field_text.casefold())
    for match in _PHONE_RE.finditer(text):
        token = match.group().strip()
        digits = re.sub(r"\D", "", token)
        has_plus = token.startswith("+")
        if has_plus:
            if len(digits) >= _MIN_PHONE_DIGITS_WITH_PLUS:
                return True
            continue
        # Без «+»: слитные цифры — не телефон, кроме 11 цифр, начинающихся с 7 или 8.
        if token.isdigit():
            if len(digits) == 11 and digits[0] in "78":
                return True
            continue
        # С разделителями.
        if len(digits) >= _MIN_PHONE_DIGITS:
            return True
    return False


def find_leaks(
    fields: Mapping[str, str],
    org_name: str,
    org_aliases: Sequence[str] = (),
) -> list[LeakViolation]:
    """Ищет утечки во всех переданных полях; результат без дубликатов, в стабильном порядке."""
    violations: list[LeakViolation] = []
    seen: set[tuple[LeakKind, str]] = set()

    for field_name, field_value in fields.items():
        if not field_value:
            continue
        if len(field_value) > _MAX_FIELD_LEN:
            raise ValueError(f"поле {field_name!r} длиннее {_MAX_FIELD_LEN} символов")
        prepared = _prepare(field_value)
        checks = (
            (LeakKind.ORG_NAME_IN_TEASER, _find_org_name(prepared, org_name, org_aliases)),
            (LeakKind.URL_IN_TEASER, _find_url(prepared)),
            (LeakKind.EMAIL_IN_TEASER, _find_email(prepared)),
            (LeakKind.PHONE_IN_TEASER, _find_phone(prepared)),
            (LeakKind.REGISTRY_ID_IN_TEASER, _find_registry_id(prepared)),
        )
        for kind, found in checks:
            if found and (kind, field_name) not in seen:
                seen.add((kind, field_name))
                violations.append(LeakViolation(code=kind, field=field_name))

    return violations
