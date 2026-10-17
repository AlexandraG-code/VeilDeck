"""Генератор синтетических PDF для seed (задача 4.4): текст без JS, вложений и шифрования."""

import pymupdf

# Дефис вместо тире: в стандартном шрифте helv тире не отображается
SYNTHETIC_MARK = "SYNTHETIC - FOR TESTING ONLY"
PAGE_WIDTH = 595
PAGE_HEIGHT = 842
MARGIN = 56
TITLE_SIZE = 18
BODY_SIZE = 11
MARK_SIZE = 10
MARK_Y = 36
TITLE_Y = 96
BODY_Y = 140
# Встроенный шрифт без кириллицы: тексты PDF только латиницей
FONT_NAME = "helv"


def build_pdf(title: str, pages: int) -> bytes:
    """Собирает PDF из `pages` страниц; пометка SYNTHETIC стоит на каждой странице."""
    document = pymupdf.open()
    for number in range(1, pages + 1):
        page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        page.insert_text((MARGIN, MARK_Y), SYNTHETIC_MARK, fontsize=MARK_SIZE, fontname=FONT_NAME)
        page.insert_textbox(
            pymupdf.Rect(MARGIN, TITLE_Y, PAGE_WIDTH - MARGIN, TITLE_Y + 2 * TITLE_SIZE),
            title,
            fontsize=TITLE_SIZE,
            fontname=FONT_NAME,
        )
        page.insert_textbox(
            pymupdf.Rect(MARGIN, BODY_Y, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN),
            f"Page {number} of {pages}. Synthetic demo material for controlled disclosure. "
            "All names, figures and organisations are fictional.",
            fontsize=BODY_SIZE,
            fontname=FONT_NAME,
        )
    try:
        return document.tobytes(garbage=3, deflate=True)
    finally:
        document.close()
