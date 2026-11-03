import io
import uuid
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible

MAX_RESUME_SIZE = 5 * 1024 * 1024
ALLOWED_RESUME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_DOCX_UNCOMPRESSED_SIZE = 50 * 1024 * 1024


@deconstructible
class PrivateStorage(FileSystemStorage):
    """Хранилище вне STATIC/MEDIA: файлы отдаются только через API с проверкой прав."""

    def __init__(self):
        super().__init__(location=settings.PRIVATE_MEDIA_ROOT, base_url=None)


def resume_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"resumes/{uuid.uuid4().hex}{extension}"


def validate_resume_file(uploaded):
    extension = Path(uploaded.name).suffix.lower()
    if extension not in ALLOWED_RESUME_TYPES:
        raise ValidationError("Допустимы только файлы PDF и DOCX.")
    if uploaded.size == 0:
        raise ValidationError("Файл пуст.")
    if uploaded.size > MAX_RESUME_SIZE:
        raise ValidationError("Размер файла не должен превышать 5 МБ.")

    uploaded.seek(0)
    content = uploaded.read()
    uploaded.seek(0)
    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise ValidationError("Содержимое файла не соответствует формату PDF.")
        return
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = set(archive.namelist())
            total = sum(item.file_size for item in archive.infolist())
    except zipfile.BadZipFile as exc:
        raise ValidationError("Содержимое файла не соответствует формату DOCX.") from exc
    if "word/document.xml" not in names or "[Content_Types].xml" not in names:
        raise ValidationError("Содержимое файла не соответствует формату DOCX.")
    if total > MAX_DOCX_UNCOMPRESSED_SIZE:
        raise ValidationError("Файл слишком велик после распаковки.")
