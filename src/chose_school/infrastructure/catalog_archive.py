from __future__ import annotations

import csv
import fnmatch
import hashlib
import io
import zipfile
from pathlib import Path
from pathlib import PurePosixPath

from chose_school.domain.models import CatalogArchive, CatalogSourceFile, RawCatalogRow
from chose_school.domain.errors import ValidationError


class KimiCatalogArchiveReader:
    """Read the five catalog CSV members without mutating the source archive."""

    def __init__(
        self,
        member_pattern: str,
        max_archive_uncompressed_bytes: int,
        max_member_uncompressed_bytes: int,
        max_compression_ratio: float,
    ) -> None:
        self._member_pattern = member_pattern
        self._max_archive_uncompressed_bytes = max_archive_uncompressed_bytes
        self._max_member_uncompressed_bytes = max_member_uncompressed_bytes
        self._max_compression_ratio = max_compression_ratio

    def source_sha256(self, archive_path: Path) -> str:
        hasher = hashlib.sha256()
        with archive_path.open("rb") as archive_file:
            for chunk in iter(lambda: archive_file.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def read(self, archive_path: Path) -> CatalogArchive:
        if not archive_path.is_file():
            raise FileNotFoundError(f"Catalog archive does not exist: {archive_path}")

        source_files: list[CatalogSourceFile] = []
        with zipfile.ZipFile(archive_path) as archive:
            self._validate_archive(archive)
            members = sorted(
                name
                for name in archive.namelist()
                if fnmatch.fnmatch(name, self._member_pattern)
            )
            if not members:
                raise ValidationError(
                    "CATALOG_MEMBERS_MISSING",
                    f"No catalog members match {self._member_pattern!r}",
                )

            for member in members:
                content = archive.read(member)
                source_files.append(self._parse_member(member, content))
            ignored_members = tuple(
                name for name in archive.namelist() if name not in members
            )
        return CatalogArchive(
            source_files=tuple(source_files),
            ignored_members=ignored_members,
        )

    def _validate_archive(self, archive: zipfile.ZipFile) -> None:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ValidationError("DUPLICATE_ARCHIVE_MEMBER", "Archive contains duplicate member names")

        total_uncompressed = 0
        for info in infos:
            member_path = PurePosixPath(info.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValidationError("UNSAFE_ARCHIVE_PATH", f"Unsafe archive member path: {info.filename}")
            if info.file_size > self._max_member_uncompressed_bytes:
                raise ValidationError("ARCHIVE_MEMBER_TOO_LARGE", f"Archive member is too large: {info.filename}")
            total_uncompressed += info.file_size
            compressed_size = max(info.compress_size, 1)
            if info.file_size / compressed_size > self._max_compression_ratio:
                raise ValidationError(
                    "UNSAFE_COMPRESSION_RATIO",
                    f"Archive member compression ratio is unsafe: {info.filename}",
                )

        if total_uncompressed > self._max_archive_uncompressed_bytes:
            raise ValidationError(
                "ARCHIVE_TOO_LARGE",
                "Archive uncompressed size exceeds configured limit",
            )

    def _parse_member(self, member: str, content: bytes) -> CatalogSourceFile:
        text = content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text, newline=""))
        try:
            header = tuple(next(reader))
        except StopIteration as error:
            raise ValidationError("EMPTY_CATALOG_MEMBER", f"Catalog member is empty: {member}") from error

        rows: list[RawCatalogRow] = []
        for row_number, cells_list in enumerate(reader, start=2):
            if not any(cell.strip() for cell in cells_list):
                continue
            cells = tuple(cells_list)
            values = {
                column: cells[index] if index < len(cells) else ""
                for index, column in enumerate(header)
            }
            rows.append(
                RawCatalogRow(
                    archive_member=member,
                    row_number=row_number,
                    header=header,
                    cells=cells,
                    values=values,
                )
            )

        return CatalogSourceFile(
            archive_member=member,
            content_sha256=hashlib.sha256(content).hexdigest(),
            header=header,
            rows=tuple(rows),
        )
