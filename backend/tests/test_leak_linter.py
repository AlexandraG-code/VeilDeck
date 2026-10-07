"""Тесты линтера утечек teaser (TC-CARD-04)."""

import time

import pytest

from app.cards.leak_linter import LeakKind, LeakViolation, find_leaks


def _codes(violations):
    """Возвращает множество кодов нарушений для удобства проверок."""
    return {v.code for v in violations}


def test_org_name_in_teaser():
    """Латинское имя организации в teaser_text даёт ровно ORG_NAME_IN_TEASER."""
    result = find_leaks(
        {
            "title_generic": "Европейский оператор грузоперевозок",
            "teaser_text": "Компания nordlicht работает в Европе.",
        },
        "Nordlicht Logistik GmbH",
    )
    assert _codes(result) == {LeakKind.ORG_NAME_IN_TEASER}
    assert all(v.field == "teaser_text" for v in result)


def test_org_name_cyrillic_in_latin_org():
    """Кириллическая запись имени при латинском org_name обнаруживается."""
    result = find_leaks(
        {"teaser_text": "Компания Газпром работает в Европе."},
        "Gazprom Neft",
    )
    assert LeakKind.ORG_NAME_IN_TEASER in _codes(result)


def test_org_name_latin_in_cyrillic_org():
    """Латинская запись имени при кириллическом org_name обнаруживается."""
    result = find_leaks(
        {"teaser_text": "Компания Severstal работает в Европе."},
        "Северсталь Групп",
    )
    assert LeakKind.ORG_NAME_IN_TEASER in _codes(result)


def test_org_name_yo_transliteration():
    """Буква «ё» транслитерируется в «e» и совпадает с латинской записью."""
    result = find_leaks(
        {"teaser_text": "Компания Samolet работает в Европе."},
        "Самолёт Девелопмент",
    )
    assert LeakKind.ORG_NAME_IN_TEASER in _codes(result)


def test_org_name_squashed_form():
    """Склеенная форма «nord licht» обнаруживается."""
    result = find_leaks(
        {"teaser_text": "Компания nord licht работает в Европе."},
        "Nordlicht Logistik GmbH",
    )
    assert LeakKind.ORG_NAME_IN_TEASER in _codes(result)


def test_org_alias_detected():
    """Алиас из org_aliases обнаруживается."""
    result = find_leaks(
        {"teaser_text": "Компания NL работает в Европе."},
        "Nordlicht Logistik GmbH",
        org_aliases=("NL",),
    )
    assert LeakKind.ORG_NAME_IN_TEASER in _codes(result)


def test_legal_form_word_alone_not_violation():
    """Слово юридической формы само по себе нарушением не является."""
    result = find_leaks(
        {"teaser_text": "Компания GmbH работает в Европе."},
        "Nordlicht Logistik GmbH",
    )
    assert LeakKind.ORG_NAME_IN_TEASER not in _codes(result)


def test_url_detected():
    """URL-подстроки (https://, www., домен) обнаруживаются."""
    for text in ("Сайт https://example.com", "Сайт www.example.de", "Сайт nordlicht.de"):
        result = find_leaks({"teaser_text": text}, "Nordlicht Logistik GmbH")
        assert LeakKind.URL_IN_TEASER in _codes(result)


def test_url_abbreviations_not_detected():
    """Сокращения «т.е.», «и.т.д.», «т. к.» не считаются URL."""
    for text in ("то есть т.е. так", "и так далее и.т.д.", "то есть т. к. так"):
        result = find_leaks({"teaser_text": text}, "Nordlicht Logistik GmbH")
        assert LeakKind.URL_IN_TEASER not in _codes(result)


def test_email_detected():
    """E-mail обнаруживается."""
    result = find_leaks({"teaser_text": "Пишите на info@example.com"}, "Nordlicht Logistik GmbH")
    assert LeakKind.EMAIL_IN_TEASER in _codes(result)


def test_phone_detected():
    """Телефонные номера с разделителями обнаруживаются."""
    for text in ("Тел. +49 30 1234567", "Тел. 8 (495) 123-45-67"):
        result = find_leaks({"teaser_text": text}, "Nordlicht Logistik GmbH")
        assert LeakKind.PHONE_IN_TEASER in _codes(result)


def test_registry_id_detected():
    """ИНН 10/12 цифр, ОГРН 13 цифр и VAT-номер дают REGISTRY_ID_IN_TEASER."""
    for text in ("ИНН 1234567890", "ИНН 123456789012", "ОГРН 1234567890123", "VAT DE123456789"):
        result = find_leaks({"teaser_text": text}, "Nordlicht Logistik GmbH")
        assert LeakKind.REGISTRY_ID_IN_TEASER in _codes(result)


def test_continuous_digits_is_registry_not_phone():
    """Слитные 10 цифр — одно нарушение REGISTRY_ID, а не PHONE."""
    for text in ("Номер 1234567890", "ИНН 1234567890 ", "ИНН 1234567890 сотрудников"):
        result = find_leaks({"teaser_text": text}, "Nordlicht Logistik GmbH")
        assert LeakKind.REGISTRY_ID_IN_TEASER in _codes(result)
        assert LeakKind.PHONE_IN_TEASER not in _codes(result)


def test_clean_text_no_violations():
    """Обычный текст с числами и годами нарушений не даёт."""
    result = find_leaks(
        {"teaser_text": "Европейская логистическая компания, около 120 сотрудников, с 2015 года, рост 35%"},
        "Nordlicht Logistik GmbH",
    )
    assert result == []


def test_fields_reported_separately_without_duplicates():
    """Нарушения в title_generic и teaser_text возвращаются раздельно, без дубликатов."""
    result = find_leaks(
        {
            "title_generic": "Nordlicht",
            "teaser_text": "Компания nordlicht, сайт nordlicht.de",
        },
        "Nordlicht Logistik GmbH",
    )
    title = [v for v in result if v.field == "title_generic"]
    teaser = [v for v in result if v.field == "teaser_text"]
    assert {v.code for v in title} == {LeakKind.ORG_NAME_IN_TEASER}
    assert LeakKind.ORG_NAME_IN_TEASER in {v.code for v in teaser}
    assert LeakKind.URL_IN_TEASER in {v.code for v in teaser}
    # Без дубликатов: каждая пара code+field встречается один раз.
    pairs = [(v.code, v.field) for v in result]
    assert len(pairs) == len(set(pairs))


def test_empty_strings_and_org_name_do_not_crash():
    """Пустые строки и пустой org_name не приводят к исключениям."""
    assert find_leaks({"title_generic": "", "teaser_text": ""}, "") == []
    assert find_leaks({"teaser_text": ""}, "Nordlicht Logistik GmbH") == []


def test_url_with_cyrillic_context():
    """URL обнаруживается в тексте с кириллицей вокруг."""
    result = find_leaks({"teaser_text": "Подробности на www.example.de"}, "Nordlicht Logistik GmbH")
    assert LeakKind.URL_IN_TEASER in _codes(result)


def test_short_alias_word_boundary():
    """Короткий алиас находится по границе слова и не находится внутри другого слова."""
    found = find_leaks(
        {"teaser_text": "Компания NL работает в Европе."},
        "Nordlicht Logistik GmbH",
        org_aliases=("NL",),
    )
    assert LeakKind.ORG_NAME_IN_TEASER in _codes(found)
    not_found = find_leaks(
        {"teaser_text": "Объект anlage в Европе."},
        "Nordlicht Logistik GmbH",
        org_aliases=("NL",),
    )
    assert LeakKind.ORG_NAME_IN_TEASER not in _codes(not_found)


def test_bypass_zero_width():
    """Zero-width и U+2011 внутри ИНН/домена/телефона не мешают обнаружению."""
    result = find_leaks({"teaser_text": "ИНН 1234\u200b567890"}, "Nordlicht Logistik GmbH")
    assert LeakKind.REGISTRY_ID_IN_TEASER in _codes(result)
    result = find_leaks({"teaser_text": "example\u200b.com"}, "Nordlicht Logistik GmbH")
    assert LeakKind.URL_IN_TEASER in _codes(result)
    result = find_leaks({"teaser_text": "+49\u200b30\u200b1234567"}, "Nordlicht Logistik GmbH")
    assert LeakKind.PHONE_IN_TEASER in _codes(result)
    result = find_leaks({"teaser_text": "+49\u201130\u20111234567"}, "Nordlicht Logistik GmbH")
    assert LeakKind.PHONE_IN_TEASER in _codes(result)


def test_bypass_arabic_indic_digits():
    """Арабско-индийские цифры в ИНН распознаются как REGISTRY_ID."""
    result = find_leaks({"teaser_text": "ИНН ١٢٣٤٥٦٧٨٩٠"}, "Nordlicht Logistik GmbH")
    assert LeakKind.REGISTRY_ID_IN_TEASER in _codes(result)


def test_bypass_diacritics_and_greek():
    """Диакритика и греческие буквы в имени обнаруживаются."""
    result = find_leaks({"teaser_text": "Nordlícht работает"}, "Nordlicht Logistik GmbH")
    assert LeakKind.ORG_NAME_IN_TEASER in _codes(result)
    result = find_leaks({"teaser_text": "Nοrdlicht работает"}, "Nordlicht Logistik GmbH")
    assert LeakKind.ORG_NAME_IN_TEASER in _codes(result)


def test_bypass_continuous_digits_phone_rules():
    """Слитные цифры без «+» и разделителей — не телефон, кроме 11 цифр с 7/8."""
    result = find_leaks({"teaser_text": "Заказ 123456789"}, "Nordlicht Logistik GmbH")
    assert result == []
    for text in ("89161234567", "79161234567"):
        result = find_leaks({"teaser_text": text}, "Nordlicht Logistik GmbH")
        assert LeakKind.PHONE_IN_TEASER in _codes(result)
    for text in ("1234567890", "123456789012", "1234567890123", "123456789012345"):
        result = find_leaks({"teaser_text": text}, "Nordlicht Logistik GmbH")
        assert LeakKind.REGISTRY_ID_IN_TEASER in _codes(result)
        assert LeakKind.PHONE_IN_TEASER not in _codes(result)


def test_bypass_false_url_cyrillic_tld():
    """Кириллический TLD не считается URL."""
    result = find_leaks({"teaser_text": "Компания работает.Она растёт"}, "Nordlicht Logistik GmbH")
    assert LeakKind.URL_IN_TEASER not in _codes(result)


def test_bypass_defang_url():
    """Дефанг-URL «[.]», «(.)», « . » распознаётся как URL."""
    for text in ("example[.]com", "example(.)com", "example . com"):
        result = find_leaks({"teaser_text": text}, "Nordlicht Logistik GmbH")
        assert LeakKind.URL_IN_TEASER in _codes(result)


def test_bypass_email_spaces():
    """E-mail с пробелами вокруг «@» и точек обнаруживается."""
    result = find_leaks({"teaser_text": "info @ example.com"}, "Nordlicht Logistik GmbH")
    assert LeakKind.EMAIL_IN_TEASER in _codes(result)
    result = find_leaks({"teaser_text": "ivan @ petrov . com"}, "Nordlicht Logistik GmbH")
    assert LeakKind.EMAIL_IN_TEASER in _codes(result)


def test_bypass_fullwidth_plus_phone():
    """Полноширинный «＋» в телефоне распознаётся как PHONE."""
    result = find_leaks({"teaser_text": "＋7 123 456 7890"}, "Nordlicht Logistik GmbH")
    assert LeakKind.PHONE_IN_TEASER in _codes(result)


def test_known_false_positive_large_money():
    """Длинные числа с разделителями дают PHONE — осознанная строгость (ложное срабатывание)."""
    result = find_leaks({"teaser_text": "1 000 000 000 руб"}, "Nordlicht Logistik GmbH")
    assert LeakKind.PHONE_IN_TEASER in _codes(result)


def test_performance_long_strings():
    """Строки длиной 4000 из повторяющихся фрагментов обрабатываются быстрее 1 с."""
    for s in ("a." * 2000, "a@" * 2000, "1-" * 2000, "а" * 4000):
        start = time.perf_counter()
        find_leaks({"teaser_text": s}, "Nordlicht Logistik GmbH")
        assert time.perf_counter() - start < 1.0


N = "Nordlicht Logistik GmbH"


@pytest.mark.parametrize(
    ("org", "text"),
    [
        (N, "Nordliсht работает"),
        (N, "Nordlіcht работает"),
        ("Bavaria Trade", "Вavaria work"),
        ("Paris Trade", "Рaris work"),
        ("Xenon Trade", "Хenon work"),
    ],
)
def test_mixed_alphabet_spoof(org, text):
    """Подмена латинских букв кириллическими гомоглифами обнаруживается."""
    result = find_leaks({"teaser_text": text}, org)
    assert LeakKind.ORG_NAME_IN_TEASER in _codes(result)


def test_pure_cyrillic_spoof():
    """Полностью кириллическая запись латинского имени обнаруживается."""
    result = find_leaks({"teaser_text": "Сосо"}, "Coco Trade")
    assert LeakKind.ORG_NAME_IN_TEASER in _codes(result)


@pytest.mark.parametrize(
    ("org", "text"),
    [
        (N, "Нордлихт"),
        ("Gazprom", "Газпром"),
        ("Северсталь Групп", "Severstal"),
    ],
)
def test_phonetic_ru_en(org, text):
    """Фонетическое соответствие русской и латинской записи обнаруживается."""
    result = find_leaks({"teaser_text": text}, org)
    assert LeakKind.ORG_NAME_IN_TEASER in _codes(result)


@pytest.mark.parametrize(
    "text",
    ["нордлихта", "NordlichtGruppe", "SuperNordlicht"],
)
def test_case_forms_and_compounds(text):
    """Падежные формы и составные слова с именем обнаруживаются."""
    result = find_leaks({"teaser_text": text}, N)
    assert LeakKind.ORG_NAME_IN_TEASER in _codes(result)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Nord licht", True),
        ("N o r d l i c h t", True),
        ("я и в этом а б с", False),
    ],
)
def test_split_name(text, expected):
    """Разделённое пробелами имя обнаруживается; посторонние буквы — нет."""
    result = find_leaks({"teaser_text": text}, N)
    assert (LeakKind.ORG_NAME_IN_TEASER in _codes(result)) is expected


@pytest.mark.parametrize(
    "text",
    ["Европейская логистика и доставка", "logistics hub", "Logistik-Zentrum", "северное сияние"],
)
def test_generic_words_not_a_leak(text):
    """Общие слова без отличительного имени нарушением не являются."""
    result = find_leaks({"teaser_text": text}, N)
    assert result == []


def test_all_generic_name():
    """Имя из одних общих слов: полное имя — нарушение, часть — нет."""
    org = "Global Trade Group"
    assert LeakKind.ORG_NAME_IN_TEASER in _codes(find_leaks({"teaser_text": "Global Trade Group"}, org))
    assert find_leaks({"teaser_text": "global trade"}, org) == []


@pytest.mark.parametrize(
    "text",
    [
        "Срок: 12.03.2015 - 14.03.2015",
        "12/03/2015–14/03/2015",
        "2015-03-12 - 2015-03-14",
        "12.03.2015",
    ],
)
def test_dates_are_not_phones(text):
    """Даты не считаются телефонными номерами."""
    result = find_leaks({"teaser_text": text}, N)
    assert LeakKind.PHONE_IN_TEASER not in _codes(result)


@pytest.mark.parametrize(
    "text",
    [
        "12.03.2015, тел. +7 999 123-45-67",
        "+7 999 123-45-67",
        "8 (999) 123 - 45 - 67",
        "99.99.2015 - 99.99.2016",
    ],
)
def test_phones_near_dates(text):
    """Телефонные номера обнаруживаются, в том числе рядом с датами."""
    result = find_leaks({"teaser_text": text}, N)
    assert LeakKind.PHONE_IN_TEASER in _codes(result)


def test_date_mask_keeps_registry():
    """Маскировка дат не ломает распознавание ИНН рядом с датой."""
    result = find_leaks({"teaser_text": "ИНН 7707083893 от 12.03.2015"}, N)
    assert LeakKind.REGISTRY_ID_IN_TEASER in _codes(result)
    assert LeakKind.PHONE_IN_TEASER not in _codes(result)


def test_performance_and_limit():
    """Длинные строки обрабатываются быстрее 1 с; поле длиннее 4096 даёт ValueError."""
    for s in ("a" * 4000, "a" * 2000 + "@" + "b" * 1000, "1 " * 2000):
        start = time.perf_counter()
        find_leaks({"teaser_text": s}, N)
        assert time.perf_counter() - start < 1.0
    with pytest.raises(ValueError):
        find_leaks({"teaser_text": "a" * 4097}, N)


@pytest.mark.parametrize(
    "text",
    [
        "Компания N L работает",
        "Компания N-L работает",
        "Компания N.L. работает",
        "Компания n l работает",
        "Компания NL работает",
    ],
)
def test_short_alias_split(text):
    """Короткий алиас «NL» с разделителями/регистром обнаруживается как ORG_NAME_IN_TEASER."""
    result = find_leaks(
        {"teaser_text": text},
        "Nordlicht Logistik GmbH",
        org_aliases=("NL",),
    )
    assert LeakKind.ORG_NAME_IN_TEASER in _codes(result)


def test_short_alias_split_negative():
    """Посторонний текст без алиаса «NL» не даёт ORG_NAME_IN_TEASER."""
    result = find_leaks(
        {"teaser_text": "Anlage und Garten"},
        "Nordlicht Logistik GmbH",
        org_aliases=("NL",),
    )
    assert LeakKind.ORG_NAME_IN_TEASER not in _codes(result)


@pytest.mark.parametrize(
    "text",
    [
        "example [.] com",
        "example [.]com",
        "example (.) com",
        "example[.] com",
        "example [.]de",
    ],
)
def test_bypass_defang_with_spaces(text):
    """Дефанг-URL с пробелами вокруг «[.]»/«(.)» распознаётся как URL_IN_TEASER."""
    result = find_leaks({"teaser_text": text}, "Nordlicht Logistik GmbH")
    assert LeakKind.URL_IN_TEASER in _codes(result)


@pytest.mark.parametrize(
    "text",
    ["Это хорошо. Она пришла", "Компания работает.Она растёт", "т.е. и.т.д."],
)
def test_bypass_defang_with_spaces_negative(text):
    """Обычные предложения и сокращения не считаются URL_IN_TEASER."""
    result = find_leaks({"teaser_text": text}, "Nordlicht Logistik GmbH")
    assert LeakKind.URL_IN_TEASER not in _codes(result)


@pytest.mark.parametrize(
    "text",
    ["сайт example.рф", "example.ру", "example.xn--p1ai"],
)
def test_url_cyrillic_and_punycode_tld(text):
    """Кириллический и punycode TLD распознаются как URL_IN_TEASER."""
    result = find_leaks({"teaser_text": text}, "Nordlicht Logistik GmbH")
    assert LeakKind.URL_IN_TEASER in _codes(result)


def test_email_cyrillic_tld():
    """E-mail с кириллическим TLD распознаётся как EMAIL_IN_TEASER."""
    result = find_leaks({"teaser_text": "info@example.рф"}, "Nordlicht Logistik GmbH")
    assert LeakKind.EMAIL_IN_TEASER in _codes(result)


def test_tc_card_04_regression():
    """Регрессия TC-CARD-04: ровно одно нарушение ORG_NAME_IN_TEASER в teaser_text."""
    result = find_leaks(
        {
            "title_generic": "Европейский оператор грузоперевозок",
            "teaser_text": "Компания nordlicht работает в Европе.",
        },
        N,
    )
    assert result == [LeakViolation(LeakKind.ORG_NAME_IN_TEASER, "teaser_text")]


def test_alias_equal_to_legal_form_word_is_still_checked():
    """Алиас, совпадающий со словом юридической формы («AB», «CO»), не отбрасывается: это искомое имя."""
    for alias, text in (("AB", "Компания AB работает"), ("CO", "Компания CO работает")):
        result = find_leaks({"teaser_text": text}, "Nordlicht Logistik GmbH", org_aliases=(alias,))
        assert [(v.code, v.field) for v in result] == [(LeakKind.ORG_NAME_IN_TEASER, "teaser_text")]


def test_legal_form_in_official_name_alone_is_not_a_leak():
    """Слово юридической формы из официального имени само по себе нарушением не является."""
    assert find_leaks({"teaser_text": "Компания GmbH работает"}, "Nordlicht Logistik GmbH") == []


def test_known_false_positives_are_documented():
    """Осознанные ложные срабатывания (сторона безопасности, остаточные риски в design.md §10).

    Короткий алиас блокирует «т.е.», голая « . » между словами читается как дефанг домена.
    """
    short = find_leaks({"teaser_text": "Это, т.е. рынок растёт"}, "Nordlicht Logistik GmbH", org_aliases=("TE",))
    assert [v.code for v in short] == [LeakKind.ORG_NAME_IN_TEASER]
    spaced_dot = find_leaks({"teaser_text": "Это хорошо . она пришла"}, "Nordlicht Logistik GmbH")
    assert [v.code for v in spaced_dot] == [LeakKind.URL_IN_TEASER]
