"""Private file storage for identity documents: on disk, never behind a URL."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateDocumentStorage(FileSystemStorage):
    """Reads PRIVATE_MEDIA_ROOT on every use, so tests and deployments can move it."""

    @property
    def base_location(self) -> Path:
        return Path(settings.PRIVATE_MEDIA_ROOT)

    @property
    def location(self) -> str:
        return str(self.base_location.resolve())

    @property
    def base_url(self) -> None:
        return None

    def url(self, name: str | None) -> str:
        raise ValueError("Identity documents are never served by URL.")


def private_storage() -> PrivateDocumentStorage:
    return PrivateDocumentStorage()
