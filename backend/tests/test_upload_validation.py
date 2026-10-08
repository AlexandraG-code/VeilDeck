"""Тесты проверки загружаемых материалов (TC-CARD-04, SR-24)."""

import hashlib
import io

import pymupdf
import pytest
from PIL import Image

from app.cards.upload_validation import (
    MAX_FILE_BYTES,
    MAX_PDF_OBJECTS,
    MAX_PDF_PAGES,
    UploadKind,
    UploadRejected,
    UploadRejectReason,
    validate_upload,
)
from app.core.errors import STATUS_BY_ERROR, VALIDATION_STATUS
from app.core.exceptions import Unprocessable

PDF_MIME = "application/pdf"
PNG_MIME = "image/png"
JPEG_MIME = "image/jpeg"
BIG_IMAGE_SIDE = 7000


def _pdf(pages: int = 1) -> bytes:
    """Простой валидный PDF с заданным числом страниц."""
    document = pymupdf.open()
    for number in range(pages):
        document.new_page().insert_text((72, 72), f"SYNTHETIC {number}")
    return document.tobytes()


def _png() -> bytes:
    """Маленький валидный PNG."""
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, "PNG")
    return buffer.getvalue()


def _jpeg() -> bytes:
    """Маленький валидный JPEG."""
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, "JPEG")
    return buffer.getvalue()


def _reason(filename: str, mime: str, data: bytes) -> UploadRejectReason:
    """Возвращает причину отказа; тест падает, если файл принят."""
    with pytest.raises(UploadRejected) as info:
        validate_upload(filename, mime, data)
    return info.value.reason


def test_valid_files_accepted():
    """PDF, PNG и JPEG принимаются; SHA-256 и размер считаются от байтов, ключ случайный."""
    for filename, mime, data, kind in (
        ("report.pdf", PDF_MIME, _pdf(2), UploadKind.PDF),
        ("scheme.png", PNG_MIME, _png(), UploadKind.PNG),
        ("photo.jpg", JPEG_MIME, _jpeg(), UploadKind.JPEG),
        ("photo.JPEG", JPEG_MIME, _jpeg(), UploadKind.JPEG),
    ):
        result = validate_upload(filename, mime, data)
        assert result.kind is kind
        assert result.mime == mime
        assert result.size == len(data)
        assert result.sha256 == hashlib.sha256(data).hexdigest()
        assert len(result.storage_key) == 32
    assert validate_upload("a.pdf", PDF_MIME, _pdf(2)).pages == 2
    assert validate_upload("a.png", PNG_MIME, _png()).pages is None


def test_storage_key_is_random_and_unrelated_to_name():
    """Две загрузки одного файла получают разные storage_key, имя в ключ не попадает."""
    data = _pdf()
    first = validate_upload("secret-name.pdf", PDF_MIME, data)
    second = validate_upload("secret-name.pdf", PDF_MIME, data)
    assert first.storage_key != second.storage_key
    assert "secret" not in first.storage_key


@pytest.mark.parametrize("filename", ["report.pdf.exe", "report.exe.pdf", "a.b.pdf", "archive.tar.gz"])
def test_double_extension_rejected(filename):
    """Двойное расширение отклоняется в любом порядке."""
    assert _reason(filename, PDF_MIME, _pdf()) in {
        UploadRejectReason.BAD_FILENAME,
        UploadRejectReason.BAD_EXTENSION,
    }


@pytest.mark.parametrize(
    "filename", ["", ".pdf", "noext", "../a.pdf", "a/b.pdf", "a\\b.pdf", "a\x00.pdf", " a.pdf", "a.pdf "]
)
def test_bad_filename_rejected(filename):
    """Пустое имя, имя без стема или расширения, разделители пути, NUL и пробелы по краям отклоняются."""
    assert _reason(filename, PDF_MIME, _pdf()) is UploadRejectReason.BAD_FILENAME


def test_filename_too_long_rejected():
    """Имя длиннее лимита отклоняется."""
    assert _reason("a" * 260 + ".pdf", PDF_MIME, _pdf()) is UploadRejectReason.BAD_FILENAME


def test_disallowed_extension_rejected():
    """Расширение не из PDF/PNG/JPEG отклоняется."""
    assert _reason("macro.docm", PDF_MIME, _pdf()) is UploadRejectReason.BAD_EXTENSION
    assert _reason("shell.exe", PDF_MIME, b"MZ\x90\x00") is UploadRejectReason.BAD_EXTENSION


def test_png_with_pdf_mime_rejected():
    """PNG с заголовком Content-Type: application/pdf отклоняется (подмена MIME)."""
    assert _reason("scheme.png", PDF_MIME, _png()) is UploadRejectReason.MIME_MISMATCH


def test_extension_disagrees_with_signature():
    """Расширение .pdf у PNG и .png у PDF отклоняются."""
    assert _reason("a.pdf", PDF_MIME, _png()) is UploadRejectReason.SIGNATURE_MISMATCH
    assert _reason("a.png", PNG_MIME, _pdf()) is UploadRejectReason.SIGNATURE_MISMATCH


def test_unknown_signature_rejected():
    """Неизвестные первые байты (исполняемый файл под видом PDF) отклоняются."""
    assert _reason("a.pdf", PDF_MIME, b"MZ\x90\x00" + b"\x00" * 100) is UploadRejectReason.SIGNATURE_MISMATCH


def test_polyglot_with_leading_bytes_rejected():
    """Сигнатура PDF не в самом начале файла (полиглот) отклоняется."""
    assert _reason("a.pdf", PDF_MIME, b"GIF89a" + _pdf()) is UploadRejectReason.SIGNATURE_MISMATCH


def test_mime_parameters_and_case_tolerated():
    """Параметры и регистр в заявленном MIME не мешают, но сам тип должен совпасть."""
    assert validate_upload("a.pdf", "Application/PDF; charset=binary", _pdf()).kind is UploadKind.PDF
    assert _reason("a.pdf", "image/png", _pdf()) is UploadRejectReason.MIME_MISMATCH
    assert _reason("a.pdf", "", _pdf()) is UploadRejectReason.MIME_MISMATCH


def test_empty_file_rejected():
    """Пустой файл отклоняется."""
    assert _reason("a.pdf", PDF_MIME, b"") is UploadRejectReason.EMPTY


def test_oversize_rejected():
    """Файл больше 10 МБ отклоняется, ровно 10 МБ по размеру не отклоняется."""
    assert _reason("a.pdf", PDF_MIME, b"%PDF-" + b"0" * MAX_FILE_BYTES) is UploadRejectReason.TOO_LARGE


def test_pdf_too_many_pages_rejected():
    """PDF на 31 страницу отклоняется, на 30 принимается."""
    assert validate_upload("a.pdf", PDF_MIME, _pdf(MAX_PDF_PAGES)).pages == MAX_PDF_PAGES
    assert _reason("a.pdf", PDF_MIME, _pdf(MAX_PDF_PAGES + 1)) is UploadRejectReason.PDF_TOO_MANY_PAGES


def test_pdf_encrypted_rejected():
    """Зашифрованный PDF отклоняется."""
    document = pymupdf.open()
    document.new_page()
    data = document.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="u", owner_pw="o")
    assert _reason("a.pdf", PDF_MIME, data) is UploadRejectReason.PDF_ENCRYPTED


def test_pdf_encrypted_with_owner_password_only_rejected():
    """Шифрование с пустым паролем пользователя (needs_pass равен False) всё равно отклоняется."""
    document = pymupdf.open()
    document.new_page()
    data = document.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="o")
    assert _reason("a.pdf", PDF_MIME, data) is UploadRejectReason.PDF_ENCRYPTED


def test_pdf_with_file_attachment_annotation_rejected():
    """Вложение через аннотацию FileAttachment (поток без /Type /EmbeddedFile) отклоняется."""
    document = pymupdf.open()
    page = document.new_page()
    stream = document.get_new_xref()
    document.update_object(stream, "<< >>")
    document.update_stream(stream, b"payload")
    annotation = document.get_new_xref()
    document.update_object(
        annotation,
        "<< /Type /Annot /Subtype /FileAttachment /Rect [0 0 10 10] "
        f"/FS << /Type /Filespec /F (x.bin) /EF << /F {stream} 0 R >> >> >>",
    )
    document.xref_set_key(page.xref, "Annots", f"[{annotation} 0 R]")
    assert _reason("a.pdf", PDF_MIME, document.tobytes()) is UploadRejectReason.PDF_ACTIVE_CONTENT


def test_pdf_engine_failure_rejected_as_malformed(monkeypatch):
    """Сбой MuPDF при анализе (не только при открытии) даёт PDF_MALFORMED, а не 500 и не пропуск."""

    class EngineError(pymupdf.mupdf.FzErrorBase):
        """Ошибка движка без обязательных аргументов конструктора."""

        def __init__(self):
            Exception.__init__(self, "boom")

    def broken(self, *args, **kwargs):
        raise EngineError()

    monkeypatch.setattr(pymupdf.Document, "xref_object", broken)
    assert _reason("a.pdf", PDF_MIME, _pdf()) is UploadRejectReason.PDF_MALFORMED


def test_pdf_with_too_many_objects_rejected(monkeypatch):
    """PDF с чрезмерным числом объектов отклоняется до перебора xref."""
    monkeypatch.setattr(pymupdf.Document, "xref_length", lambda self: MAX_PDF_OBJECTS + 1)
    assert _reason("a.pdf", PDF_MIME, _pdf()) is UploadRejectReason.PDF_MALFORMED


def test_pdf_with_javascript_rejected():
    """PDF с JavaScript в действии открытия отклоняется."""
    document = pymupdf.open()
    document.new_page()
    xref = document.get_new_xref()
    document.update_object(xref, "<< /S /JavaScript /JS (app.alert(1)) >>")
    catalog = document.pdf_catalog()
    document.xref_set_key(catalog, "OpenAction", f"{xref} 0 R")
    assert _reason("a.pdf", PDF_MIME, document.tobytes()) is UploadRejectReason.PDF_ACTIVE_CONTENT


def test_pdf_with_obfuscated_javascript_name_rejected():
    """Имя /JavaScript, записанное через #-кодирование, тоже отклоняется."""
    document = pymupdf.open()
    document.new_page()
    xref = document.get_new_xref()
    document.update_object(xref, "<< /S /Java#53cript /J#53 (app.alert(1)) >>")
    document.xref_set_key(document.pdf_catalog(), "OpenAction", f"{xref} 0 R")
    assert _reason("a.pdf", PDF_MIME, document.tobytes()) is UploadRejectReason.PDF_ACTIVE_CONTENT


def test_pdf_with_embedded_file_rejected():
    """PDF со встроенным файлом отклоняется."""
    document = pymupdf.open()
    document.new_page()
    document.embfile_add("payload.bin", b"data")
    assert _reason("a.pdf", PDF_MIME, document.tobytes()) is UploadRejectReason.PDF_ACTIVE_CONTENT


def test_pdf_with_launch_action_rejected():
    """PDF с действием Launch отклоняется."""
    document = pymupdf.open()
    document.new_page()
    xref = document.get_new_xref()
    document.update_object(xref, "<< /S /Launch /F (cmd.exe) >>")
    document.xref_set_key(document.pdf_catalog(), "OpenAction", f"{xref} 0 R")
    assert _reason("a.pdf", PDF_MIME, document.tobytes()) is UploadRejectReason.PDF_ACTIVE_CONTENT


@pytest.mark.parametrize(
    "action",
    [
        "<< /S /SubmitForm /F (http://x.example/) >>",
        "<< /S /ImportData /F (a.fdf) >>",
        "<< /S /GoToR /F (other.pdf) /D [0 /Fit] >>",
        "<< /S /GoToE /T << /R /C /N (x) >> >>",
        "<< /S /Movie /T (m) >>",
        "<< /S /Sound /Sound 1 0 R >>",
        "<< /S /Rendition /OP 0 >>",
    ],
)
def test_pdf_with_other_active_actions_rejected(action):
    """Действия, которые отправляют данные наружу или открывают внешний ресурс, отклоняются."""
    document = pymupdf.open()
    document.new_page()
    xref = document.get_new_xref()
    document.update_object(xref, action)
    document.xref_set_key(document.pdf_catalog(), "OpenAction", f"{xref} 0 R")
    assert _reason("a.pdf", PDF_MIME, document.tobytes()) is UploadRejectReason.PDF_ACTIVE_CONTENT


def test_pdf_with_additional_actions_rejected():
    """PDF с дополнительными действиями /AA в каталоге отклоняется."""
    document = pymupdf.open()
    document.new_page()
    xref = document.get_new_xref()
    document.update_object(xref, "<< /S /GoTo /D [0 /Fit] >>")
    document.xref_set_key(document.pdf_catalog(), "AA", f"<< /WC {xref} 0 R >>")
    assert _reason("a.pdf", PDF_MIME, document.tobytes()) is UploadRejectReason.PDF_ACTIVE_CONTENT


@pytest.mark.parametrize(
    "uri",
    [
        "https://api.example.com/JSON/docs",
        "https://example.com/AAPL-report",
        "https://example.com/docs/JS-guide",
        "https://example.com/a(b)/AA/c",
    ],
)
def test_pdf_with_safe_link_containing_marker_substring_accepted(uri):
    """URL со вхождениями /JS, /AA в строковом литерале не считается активным содержимым."""
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "SYNTHETIC")
    page.insert_link({"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(72, 60, 200, 80), "uri": uri})
    assert validate_upload("a.pdf", PDF_MIME, document.tobytes()).pages == 1


def test_pdf_with_toc_title_containing_marker_substring_accepted():
    """Заголовок оглавления с текстом /AA и /JS не даёт ложного срабатывания."""
    document = pymupdf.open()
    document.new_page()
    document.set_toc([[1, "Раздел /AA и /JS и /JavaScript", 1]])
    assert validate_upload("a.pdf", PDF_MIME, document.tobytes()).pages == 1


def test_pdf_with_internal_link_and_text_accepted():
    """Обычный PDF с внутренней ссылкой и текстом принимается."""
    document = pymupdf.open()
    document.new_page()
    page = document.new_page()
    page.insert_text((72, 72), "SYNTHETIC")
    document[0].insert_link({"kind": pymupdf.LINK_GOTO, "from": pymupdf.Rect(0, 0, 50, 50), "page": 1})
    assert validate_upload("a.pdf", PDF_MIME, document.tobytes()).pages == 2


def test_pdf_javascript_after_string_with_escaped_parens_rejected():
    """Экранированные скобки в строке не сбивают разбор: активное имя после строки находится."""
    document = pymupdf.open()
    document.new_page()
    xref = document.get_new_xref()
    document.update_object(xref, "<< /Note (a \\) b \\( c) /S /JavaScript /JS (x) >>")
    document.xref_set_key(document.pdf_catalog(), "OpenAction", f"{xref} 0 R")
    assert _reason("a.pdf", PDF_MIME, document.tobytes()) is UploadRejectReason.PDF_ACTIVE_CONTENT


def test_pillow_global_limit_not_modified():
    """Проверка изображения не меняет глобальный лимит Pillow (потокобезопасность)."""
    before = Image.MAX_IMAGE_PIXELS
    validate_upload("a.png", PNG_MIME, _png())
    _reason("a.png", PNG_MIME, b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    assert Image.MAX_IMAGE_PIXELS == before


def test_broken_pdf_rejected():
    """Обрезанный или мусорный PDF отклоняется как повреждённый."""
    assert _reason("a.pdf", PDF_MIME, b"%PDF-1.7\ngarbage") is UploadRejectReason.PDF_MALFORMED


def test_broken_image_rejected():
    """Изображение с верной сигнатурой, но мусорным телом отклоняется."""
    assert _reason("a.png", PNG_MIME, b"\x89PNG\r\n\x1a\n" + b"\x00" * 64) is UploadRejectReason.IMAGE_MALFORMED
    assert _reason("a.jpg", JPEG_MIME, b"\xff\xd8\xff" + b"\x00" * 64) is UploadRejectReason.IMAGE_MALFORMED


def test_image_pixel_bomb_rejected():
    """Изображение с огромным числом пикселей при малом размере файла отклоняется."""
    buffer = io.BytesIO()
    Image.new("1", (BIG_IMAGE_SIDE, BIG_IMAGE_SIDE)).save(buffer, "PNG")
    assert len(buffer.getvalue()) < MAX_FILE_BYTES
    assert _reason("a.png", PNG_MIME, buffer.getvalue()) is UploadRejectReason.IMAGE_TOO_LARGE


def test_png_declared_as_jpeg_rejected():
    """PNG под расширением .jpg и MIME image/jpeg отклоняется."""
    assert _reason("a.jpg", JPEG_MIME, _png()) is UploadRejectReason.SIGNATURE_MISMATCH


def test_rejection_does_not_leak_filename():
    """В тексте и атрибутах ошибки нет имени файла (SR-21)."""
    with pytest.raises(UploadRejected) as info:
        validate_upload("confidential-nordlicht.pdf.exe", PDF_MIME, _pdf())
    assert "nordlicht" not in str(info.value)
    assert "nordlicht" not in repr(vars(info.value))


def test_rejection_maps_to_422():
    """Отказ загрузки превращается в HTTP 422 (spec card-management: ответ 422)."""
    assert issubclass(UploadRejected, Unprocessable)
    assert STATUS_BY_ERROR[Unprocessable] == VALIDATION_STATUS
