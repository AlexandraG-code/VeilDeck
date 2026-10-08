"""Проверка загружаемых материалов: чистая функция без FastAPI и БД (SR-24, T-11, TC-CARD-04).

Принимает имя файла, заявленный MIME и байты. Возвращает описание проверенного файла или бросает UploadRejected.
Расширение, заявленный MIME и сигнатура (magic bytes) должны указывать на один и тот же тип из PDF/PNG/JPEG.
PDF с шифрованием, JavaScript, встроенными файлами и активным содержимым отклоняется. Имя файла и его фрагменты
нигде не печатаются и не попадают в сообщение об ошибке: в отказ кладётся только машинный код причины.
Количество файлов на карточку (MAX_FILES_PER_CARD) проверяет сервис, у него есть доступ к БД.
"""

import hashlib
import io
import re
import uuid
from dataclasses import dataclass
from enum import StrEnum

import pymupdf
from PIL import Image, UnidentifiedImageError

from app.core.exceptions import Unprocessable

# Максимальный размер файла: 10 МБ.
MAX_FILE_BYTES = 10 * 1024 * 1024
# Максимальное число файлов на карточку (проверяет сервис).
MAX_FILES_PER_CARD = 10
# Максимальное число страниц PDF.
MAX_PDF_PAGES = 30
# Максимальное число объектов PDF (защита от долгого перебора xref).
MAX_PDF_OBJECTS = 100_000
# Ошибки движка PDF: у MuPDF свой базовый класс, не RuntimeError.
_PDF_ENGINE_ERRORS = (pymupdf.mupdf.FzErrorBase, RuntimeError, ValueError)
# Максимальное число пикселей изображения (защита от decompression bomb).
MAX_IMAGE_PIXELS = 40_000_000
# Максимальная длина имени файла.
MAX_FILENAME_LEN = 255
# Сигнатуры форматов.
_PDF_SIGNATURE = b"%PDF-"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"
# Имена PDF, означающие активное содержимое (без ведущего «/»).
_PDF_ACTIVE_NAMES = (
    "JS",
    "JavaScript",
    "Launch",
    "SubmitForm",
    "ImportData",
    "GoToR",
    "GoToE",
    "AA",
    "Movie",
    "Sound",
    "Rendition",
    "RichMedia",
    "EmbeddedFile",
    "EF",
    "FileAttachment",
    "3D",
    "XFA",
)
# Имя целиком: после него пробел, разделитель PDF или конец объекта (поэтому /JSON и /AAPL не совпадают с /JS и /AA).
_PDF_ACTIVE_PATTERN = re.compile("/(?:" + "|".join(_PDF_ACTIVE_NAMES) + r")(?=[\s()<>\[\]{}/%]|$)")
# Запрещённые символы в имени файла: разделители пути, управляющие символы.
_BAD_FILENAME = re.compile(r"[\x00-\x1f\x7f/\\]")


class UploadKind(StrEnum):
    """Допустимые типы материалов."""

    PDF = "pdf"
    PNG = "png"
    JPEG = "jpeg"


class UploadRejectReason(StrEnum):
    """Причина отказа: машинный код для аудита (событие material.upload_rejected), без данных файла."""

    EMPTY = "empty"
    TOO_LARGE = "too_large"
    BAD_FILENAME = "bad_filename"
    BAD_EXTENSION = "bad_extension"
    SIGNATURE_MISMATCH = "signature_mismatch"
    MIME_MISMATCH = "mime_mismatch"
    PDF_MALFORMED = "pdf_malformed"
    PDF_ENCRYPTED = "pdf_encrypted"
    PDF_TOO_MANY_PAGES = "pdf_too_many_pages"
    PDF_ACTIVE_CONTENT = "pdf_active_content"
    IMAGE_MALFORMED = "image_malformed"
    IMAGE_TOO_LARGE = "image_too_large"


class UploadRejected(Unprocessable):
    """Файл не прошёл проверку; reason идёт в аудит, клиенту отдаётся общее сообщение."""

    code = "upload_rejected"
    message = "Файл не принят"

    def __init__(self, reason: UploadRejectReason) -> None:
        self.reason = reason
        super().__init__()


@dataclass(frozen=True)
class ValidatedUpload:
    """Результат проверки: всё, что нужно сохранить в БД и на диск."""

    kind: UploadKind
    mime: str
    size: int
    sha256: str
    storage_key: str
    pages: int | None


_MIME_BY_KIND = {UploadKind.PDF: "application/pdf", UploadKind.PNG: "image/png", UploadKind.JPEG: "image/jpeg"}
_KIND_BY_EXTENSION = {"pdf": UploadKind.PDF, "png": UploadKind.PNG, "jpg": UploadKind.JPEG, "jpeg": UploadKind.JPEG}
_IMAGE_FORMAT_BY_KIND = {UploadKind.PNG: "PNG", UploadKind.JPEG: "JPEG"}


def validate_upload(filename: str, declared_mime: str, data: bytes) -> ValidatedUpload:
    """Проверяет файл целиком и возвращает его описание; при любом несоответствии бросает UploadRejected."""
    _check_size(data)
    kind_by_name = _kind_from_filename(filename)
    kind = _kind_from_signature(data)
    if kind is not kind_by_name:
        raise UploadRejected(UploadRejectReason.SIGNATURE_MISMATCH)
    if _normalize_mime(declared_mime) != _MIME_BY_KIND[kind]:
        raise UploadRejected(UploadRejectReason.MIME_MISMATCH)
    pages = None
    if kind is UploadKind.PDF:
        pages = _check_pdf(data)
    else:
        _check_image(data, kind)
    return ValidatedUpload(
        kind=kind,
        mime=_MIME_BY_KIND[kind],
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        storage_key=uuid.uuid4().hex,
        pages=pages,
    )


def _check_size(data: bytes) -> None:
    """Файл не пустой и не больше MAX_FILE_BYTES."""
    if not data:
        raise UploadRejected(UploadRejectReason.EMPTY)
    if len(data) > MAX_FILE_BYTES:
        raise UploadRejected(UploadRejectReason.TOO_LARGE)


def _kind_from_filename(filename: str) -> UploadKind:
    """Тип по расширению. Ровно одно расширение: report.pdf.exe и report.exe.pdf отклоняются."""
    if not filename or len(filename) > MAX_FILENAME_LEN or _BAD_FILENAME.search(filename):
        raise UploadRejected(UploadRejectReason.BAD_FILENAME)
    stem, dot, extension = filename.rpartition(".")
    if not dot or not stem or "." in stem or filename != filename.strip():
        raise UploadRejected(UploadRejectReason.BAD_FILENAME)
    kind = _KIND_BY_EXTENSION.get(extension.lower())
    if kind is None:
        raise UploadRejected(UploadRejectReason.BAD_EXTENSION)
    return kind


def _kind_from_signature(data: bytes) -> UploadKind:
    """Тип по первым байтам файла: сигнатура должна стоять в самом начале (полиглоты отклоняются)."""
    if data.startswith(_PDF_SIGNATURE):
        return UploadKind.PDF
    if data.startswith(_PNG_SIGNATURE):
        return UploadKind.PNG
    if data.startswith(_JPEG_SIGNATURE):
        return UploadKind.JPEG
    raise UploadRejected(UploadRejectReason.SIGNATURE_MISMATCH)


def _normalize_mime(declared_mime: str) -> str:
    """Заявленный MIME без параметров и регистра."""
    return declared_mime.split(";", 1)[0].strip().lower()


def _check_image(data: bytes, kind: UploadKind) -> None:
    """Изображение декодируется, формат совпадает с типом, число пикселей ограничено до декодирования.

    Глобальные настройки Pillow не меняются (функция вызывается из потоков): размеры читаются из заголовка в open().
    """
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format != _IMAGE_FORMAT_BY_KIND[kind]:
                raise UploadRejected(UploadRejectReason.SIGNATURE_MISMATCH)
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise UploadRejected(UploadRejectReason.IMAGE_TOO_LARGE)
            image.load()
    except Image.DecompressionBombError as exc:
        raise UploadRejected(UploadRejectReason.IMAGE_TOO_LARGE) from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise UploadRejected(UploadRejectReason.IMAGE_MALFORMED) from exc


def _check_pdf(data: bytes) -> int:
    """PDF открывается, не зашифрован, ≤ MAX_PDF_PAGES страниц, без JS, встроенных файлов и активного содержимого."""
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
        with document:
            return _inspect_pdf(document)
    except _PDF_ENGINE_ERRORS as exc:
        raise UploadRejected(UploadRejectReason.PDF_MALFORMED) from exc


def _inspect_pdf(document: pymupdf.Document) -> int:
    """Проверяет открытый документ и возвращает число страниц. Сбой разбора не пропускается: он даёт PDF_MALFORMED."""
    if document.needs_pass or document.is_encrypted or _has_encrypt_dictionary(document):
        raise UploadRejected(UploadRejectReason.PDF_ENCRYPTED)
    if document.page_count < 1 or document.xref_length() > MAX_PDF_OBJECTS:
        raise UploadRejected(UploadRejectReason.PDF_MALFORMED)
    if document.page_count > MAX_PDF_PAGES:
        raise UploadRejected(UploadRejectReason.PDF_TOO_MANY_PAGES)
    if document.embfile_count() or _has_active_content(document):
        raise UploadRejected(UploadRejectReason.PDF_ACTIVE_CONTENT)
    return document.page_count


def _has_encrypt_dictionary(document: pymupdf.Document) -> bool:
    """В trailer есть /Encrypt: шифрование с пустым паролем пользователя needs_pass не выдаёт."""
    return document.xref_get_key(-1, "Encrypt")[0] != "null"


def _strip_literal_strings(body: str) -> str:
    """Заменяет строковые литералы PDF «(...)» пробелом: URL и тексты не должны давать ложных срабатываний.

    Учитываются экранирование «\\» и вложенные скобки (в PDF непарные скобки в литерале экранируются).
    """
    result: list[str] = []
    depth = 0
    escaped = False
    for char in body:
        if depth == 0:
            if char == "(":
                depth = 1
                result.append(" ")
            else:
                result.append(char)
        elif escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
    return "".join(result)


def _has_active_content(document: pymupdf.Document) -> bool:
    """Ищет признаки JavaScript и активного содержимого во всех объектах PDF (включая каталог и аннотации)."""
    for xref in range(1, document.xref_length()):
        body = document.xref_object(xref, compressed=False)
        if _PDF_ACTIVE_PATTERN.search(_strip_literal_strings(body)):
            return True
    return False
