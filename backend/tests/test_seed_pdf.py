"""Синтетические PDF для seed (4.4): проходят проверку загрузки и несут пометку SYNTHETIC на каждой странице."""

import pymupdf

from app.cards.upload_validation import validate_upload
from scripts.synthetic_pdf import SYNTHETIC_MARK, build_pdf

PAGES = 3


def test_seed_pdf_passes_upload_validation() -> None:
    """TC-CARD-04: сид-материал не отличается от допустимой загрузки (без JS, вложений, шифрования)."""
    data = build_pdf("Synthetic material", PAGES)
    assert validate_upload("seed.pdf", "application/pdf", data).pages == PAGES


def test_seed_pdf_marks_every_page() -> None:
    """Пометка «SYNTHETIC — FOR TESTING ONLY» стоит на каждой странице."""
    document = pymupdf.open(stream=build_pdf("Synthetic material", PAGES), filetype="pdf")
    assert all(SYNTHETIC_MARK in page.get_text() for page in document)
