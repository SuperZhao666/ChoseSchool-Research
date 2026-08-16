from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
import uuid
from contextlib import closing
from pathlib import Path

from tests.support import REPOSITORY_ROOT

from chose_school.data_access.sqlite_catalog import (
    SqliteCatalogRepository,
    _evidence_source_metadata_correction_fingerprint,
)
from chose_school.infrastructure.database import Database


MIGRATION_DIRECTORY = (
    REPOSITORY_ROOT / "src" / "chose_school" / "infrastructure" / "migrations"
)
NCU_SOURCE_HASH = (
    "92cbb1ec97347292ad9dddf77a3a4aac98900274b47cad439ad59dc34bb64c7c"
)
NCU_SOURCE_IDENTITIES = (
    "a0f610b3532fa8f89f52bed5bcef29b4080e37deaf7209296e9667211f55e449",
    "73b98d3fce8726d8a900c1d3bf8a8a7df68f3fa8a9235beee6a8af84bc78c47b",
)
LNU_SOURCE_IDENTITY = (
    "dbced694ad90eb3d222d472351c2f2853abeefaedfd55bec8e8329efe483b02e"
)
LNU_SOURCE_HASH = (
    "a923c330057d4478aae158aae27cf190e07ae7232988e46d9567909364918957"
)
LNU_ORIGINAL_NOTE = "逐行剔除调剂、非全和专项；本项目名单均为一志愿全日制非定向。"
LNU_EFFECTIVE_NOTE = (
    "该原件仅能证明名单列示的专业代码、一志愿、全日制和非定向属性；"
    "名单无专项计划列，不能据此排除专项。各项目行数须在项目级事实中记录。"
)
SWJTU_SOURCE_IDENTITY = (
    "b1ace4aa435a69ad9f13688f1c5e4559ae81e0459a7be0faad206a5955349a1f"
)
EXPECTED_SEED_FINGERPRINTS = {
    NCU_SOURCE_IDENTITIES[0]: (
        "e93839bf2b6490c9af24002a610c2ce353560ca4473a86e525dae1c2f0c3ef5d"
    ),
    NCU_SOURCE_IDENTITIES[1]: (
        "9aac0cf9b5d78711c6246477a99160fac4bbedd0706728ee8f9f26413df1b7a3"
    ),
    LNU_SOURCE_IDENTITY: (
        "d8f216e8296c429ed91830e31763691c94ecb61d5edeee56be829384ad1cdb92"
    ),
}


class EvidenceSourceMetadataCorrectionTest(unittest.TestCase):
    def test_seed_backfill_is_identity_and_hash_bound_with_effective_metadata(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = _build_seeded_database(Path(temporary))
            repository = SqliteCatalogRepository(Database(database_path))

            with closing(sqlite3.connect(database_path)) as connection:
                connection.row_factory = sqlite3.Row
                corrections = connection.execute(
                    """
                    SELECT
                        source.identity_key AS source_identity_key,
                        correction.*,
                        predecessor.correction_fingerprint
                            AS supersedes_correction_fingerprint
                    FROM evidence_source_metadata_corrections correction
                    JOIN evidence_sources source ON source.id = correction.source_id
                    LEFT JOIN evidence_source_metadata_corrections predecessor
                      ON predecessor.id = correction.supersedes_correction_id
                    ORDER BY correction.id
                    """
                ).fetchall()
                effective = {
                    row["identity_key"]: row
                    for row in connection.execute(
                        "SELECT * FROM v_evidence_sources_effective"
                    )
                }
                audit_counts = connection.execute(
                    """
                    SELECT COUNT(*) AS event_count,
                           COUNT(DISTINCT entity_id) AS entity_count
                    FROM audit_events
                    WHERE event_type = 'evidence_source_metadata_corrected'
                      AND entity_type = 'evidence_source_metadata_correction'
                    """
                ).fetchone()

            self.assertEqual(len(corrections), 3)
            self.assertEqual(
                {row["source_identity_key"] for row in corrections},
                set(EXPECTED_SEED_FINGERPRINTS),
            )
            self.assertEqual(
                {
                    row["source_identity_key"]: row["correction_fingerprint"]
                    for row in corrections
                },
                EXPECTED_SEED_FINGERPRINTS,
            )
            for row in corrections:
                self.assertEqual(
                    row["correction_fingerprint"],
                    _evidence_source_metadata_correction_fingerprint(row),
                )
                self.assertIsNone(row["supersedes_correction_id"])

            for identity_key in NCU_SOURCE_IDENTITIES:
                row = effective[identity_key]
                self.assertEqual(row["original_published_date"], "2025-10-15")
                self.assertEqual(row["effective_published_date"], "2025-09-30")
                self.assertEqual(row["published_date"], "2025-09-30")
                self.assertEqual(
                    row["published_date_correction_source_content_sha256"],
                    NCU_SOURCE_HASH,
                )
                self.assertEqual(
                    row["published_date_prior_effective_value"], "2025-10-15"
                )
                self.assertIsNotNone(row["published_date_correction_basis_url"])
                self.assertIsNotNone(row["published_date_correction_trace_id"])

            lnu = effective[LNU_SOURCE_IDENTITY]
            self.assertEqual(lnu["original_source_note"], LNU_ORIGINAL_NOTE)
            self.assertEqual(lnu["effective_source_note"], LNU_EFFECTIVE_NOTE)
            self.assertEqual(lnu["source_note"], LNU_EFFECTIVE_NOTE)
            self.assertNotIn("018-085405", lnu["effective_source_note"])
            self.assertNotIn("22 行", lnu["effective_source_note"])

            # The same NCU bytes under a different identity must not be corrected.
            decoy = effective["f" * 64]
            self.assertEqual(decoy["effective_published_date"], "2025-10-15")
            self.assertIsNone(decoy["published_date_correction_id"])

            # This shared SWJTU source deliberately has no source-level correction.
            swjtu = effective[SWJTU_SOURCE_IDENTITY]
            self.assertEqual(swjtu["source_note"], swjtu["original_source_note"])
            self.assertIsNone(swjtu["source_note_correction_id"])
            self.assertEqual(tuple(audit_counts), (3, 3))

            doctor = repository.doctor()
            self.assertEqual(doctor["status"], "ok")
            self.assertEqual(doctor["evidence_source_metadata_correction_count"], 3)
            for name, value in doctor.items():
                if name.startswith("evidence_source_correction_"):
                    self.assertEqual(value, 0, name)

    def test_successor_is_a_single_hash_bound_append_only_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = _build_seeded_database(Path(temporary))
            repository = SqliteCatalogRepository(Database(database_path))

            with closing(sqlite3.connect(database_path)) as connection:
                connection.row_factory = sqlite3.Row
                root = connection.execute(
                    """
                    SELECT correction.*, source.identity_key AS source_identity_key
                    FROM evidence_source_metadata_corrections correction
                    JOIN evidence_sources source ON source.id = correction.source_id
                    WHERE source.identity_key = ?
                    """,
                    (NCU_SOURCE_IDENTITIES[0],),
                ).fetchone()
                successor = {
                    "source_identity_key": root["source_identity_key"],
                    "source_content_sha256": root["source_content_sha256"],
                    "field_name": "published_date",
                    "prior_effective_value": root["corrected_value"],
                    "corrected_value": "2025-09-29",
                    "supersedes_correction_fingerprint": root[
                        "correction_fingerprint"
                    ],
                    "basis_url": "https://example.edu/official/date-clarification",
                    "basis_content_sha256": "f" * 64,
                    "basis_retrieved_date": "2026-08-13",
                    "reason": "独立官方页面进一步澄清发布日期。",
                }
                successor_fingerprint = (
                    _evidence_source_metadata_correction_fingerprint(successor)
                )
                connection.execute(
                    """
                    INSERT INTO evidence_source_metadata_corrections(
                        correction_fingerprint, source_id, source_content_sha256,
                        field_name, prior_effective_value, corrected_value,
                        supersedes_correction_id, basis_url,
                        basis_content_sha256, basis_retrieved_date, reason,
                        trace_id, created_at
                    ) VALUES (?, ?, ?, 'published_date', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        successor_fingerprint,
                        root["source_id"],
                        root["source_content_sha256"],
                        root["corrected_value"],
                        successor["corrected_value"],
                        root["id"],
                        successor["basis_url"],
                        successor["basis_content_sha256"],
                        successor["basis_retrieved_date"],
                        successor["reason"],
                        str(uuid.uuid4()),
                        "2026-08-13T11:00:00+08:00",
                    ),
                )

                current = connection.execute(
                    """
                    SELECT correction.*
                    FROM v_current_evidence_source_metadata_corrections correction
                    WHERE correction.source_id = ?
                      AND correction.field_name = 'published_date'
                    """,
                    (root["source_id"],),
                ).fetchone()
                effective = connection.execute(
                    "SELECT * FROM v_evidence_sources_effective WHERE id = ?",
                    (root["source_id"],),
                ).fetchone()
                self.assertEqual(current["correction_fingerprint"], successor_fingerprint)
                self.assertEqual(effective["original_published_date"], "2025-10-15")
                self.assertEqual(effective["published_date"], "2025-09-29")
                self.assertEqual(
                    effective["published_date_supersedes_correction_id"], root["id"]
                )

                with self.assertRaises(sqlite3.IntegrityError):
                    _insert_branch(connection, root, "1" * 64)
                with self.assertRaises(sqlite3.IntegrityError):
                    _insert_branch(connection, root, "2" * 64, source_hash="0" * 64)
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "UPDATE evidence_source_metadata_corrections SET reason = '覆盖'"
                    )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "DELETE FROM evidence_source_metadata_corrections WHERE id = ?",
                        (root["id"],),
                    )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "UPDATE evidence_sources SET title = '覆盖' WHERE id = ?",
                        (root["source_id"],),
                    )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "DELETE FROM evidence_sources WHERE id = ?", (root["source_id"],)
                    )
                connection.execute(
                    "UPDATE evidence_sources SET updated_at = ? WHERE id = ?",
                    ("2026-08-13T11:01:00+08:00", root["source_id"]),
                )
                connection.commit()

                audit_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM audit_events
                    WHERE event_type = 'evidence_source_metadata_corrected'
                      AND entity_type = 'evidence_source_metadata_correction'
                    """
                ).fetchone()[0]
                self.assertEqual(audit_count, 4)

            doctor = repository.doctor()
            self.assertEqual(doctor["status"], "ok")
            self.assertEqual(doctor["evidence_source_metadata_correction_count"], 4)

    def test_doctor_recomputes_canonical_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = _build_seeded_database(Path(temporary))
            repository = SqliteCatalogRepository(Database(database_path))

            with closing(sqlite3.connect(database_path)) as connection:
                source_id = connection.execute(
                    """
                    INSERT INTO evidence_sources(
                        identity_key, title, institution, url, evidence_grade,
                        published_date, retrieved_date, source_note,
                        created_at, updated_at, document_type,
                        content_sha256, applicable_year
                    ) VALUES (?, '测试来源', '测试机构', 'https://example.edu/source',
                              'official', NULL, '2026-08-13', NULL,
                              '2026-08-13T12:00:00+08:00',
                              '2026-08-13T12:00:00+08:00',
                              'official_notice', ?, 2026)
                    """,
                    ("e" * 64, "d" * 64),
                ).lastrowid
                connection.execute(
                    """
                    INSERT INTO evidence_source_metadata_corrections(
                        correction_fingerprint, source_id, source_content_sha256,
                        field_name, prior_effective_value, corrected_value,
                        supersedes_correction_id, basis_url,
                        basis_content_sha256, basis_retrieved_date, reason,
                        trace_id, created_at
                    ) VALUES (?, ?, ?, 'source_note', NULL, '有效说明', NULL,
                              'https://example.edu/basis', ?, '2026-08-13',
                              '测试非规范指纹。', ?, '2026-08-13T12:01:00+08:00')
                    """,
                    ("0" * 64, source_id, "d" * 64, "c" * 64, str(uuid.uuid4())),
                )
                connection.commit()

            doctor = repository.doctor()
            self.assertEqual(doctor["status"], "error")
            self.assertEqual(
                doctor["evidence_source_correction_fingerprint_mismatch"], 1
            )


def _build_seeded_database(root: Path) -> Path:
    database_path = root / "metadata-corrections.sqlite3"
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                filename TEXT NOT NULL UNIQUE,
                checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        for migration_path in sorted(
            MIGRATION_DIRECTORY.glob("[0-9][0-9][0-9]_*.sql")
        ):
            version = int(migration_path.name.split("_", 1)[0])
            if version >= 24:
                break
            sql = migration_path.read_text(encoding="utf-8")
            connection.executescript(sql)
            connection.execute(
                "INSERT INTO schema_migrations VALUES (?, ?, ?, ?)",
                (
                    version,
                    migration_path.name,
                    hashlib.sha256(sql.encode("utf-8")).hexdigest(),
                    "2026-08-13T00:00:00+00:00",
                ),
            )

        _insert_source(
            connection,
            identity_key=NCU_SOURCE_IDENTITIES[0],
            title="南昌大学2026年硕士研究生招生专业目录（验证引用一）",
            url="https://yjsy.ncu.edu.cn/catalog.pdf",
            published_date="2025-10-15",
            source_note=None,
            content_sha256=NCU_SOURCE_HASH,
            document_type="official_catalog",
        )
        _insert_source(
            connection,
            identity_key=NCU_SOURCE_IDENTITIES[1],
            title="南昌大学2026年硕士研究生招生专业目录（验证引用二）",
            url="https://yjsy.ncu.edu.cn/catalog.pdf",
            published_date="2025-10-15",
            source_note=None,
            content_sha256=NCU_SOURCE_HASH,
            document_type="official_catalog",
        )
        _insert_source(
            connection,
            identity_key=LNU_SOURCE_IDENTITY,
            title="辽宁大学2026年硕士研究生一志愿拟录取名单",
            url="https://grs.lnu.edu.cn/2026ssyzymd.pdf",
            published_date=None,
            source_note=LNU_ORIGINAL_NOTE,
            content_sha256=LNU_SOURCE_HASH,
            document_type="admission_list",
        )
        _insert_source(
            connection,
            identity_key="f" * 64,
            title="相同字节但不同来源身份的对照记录",
            url="https://example.edu/decoy.pdf",
            published_date="2025-10-15",
            source_note=None,
            content_sha256=NCU_SOURCE_HASH,
            document_type="official_catalog",
        )
        _insert_source(
            connection,
            identity_key=SWJTU_SOURCE_IDENTITY,
            title="西南交通大学2026年硕士研究生拟录取名单",
            url=(
                "https://yz.swjtu.edu.cn/download/ueditor/jsp/upload/file/"
                "20260424/1777011358828064776.pdf"
            ),
            published_date=None,
            source_note=(
                "官方名单第104-105页；另有2名退役大学生士兵计划，"
                "不计入普通统考42人。"
            ),
            content_sha256=(
                "b7a8039379153511e5a62ffe319a326baa271be16768ca9100134a367a10a95a"
            ),
            document_type="admission_list",
        )

        migration_path = (
            MIGRATION_DIRECTORY / "024_add_evidence_source_metadata_corrections.sql"
        )
        sql = migration_path.read_text(encoding="utf-8")
        connection.executescript(sql)
        connection.execute(
            "INSERT INTO schema_migrations VALUES (24, ?, ?, ?)",
            (
                migration_path.name,
                hashlib.sha256(sql.encode("utf-8")).hexdigest(),
                "2026-08-13T00:00:00+00:00",
            ),
        )
        connection.commit()
    return database_path


def _insert_source(
    connection: sqlite3.Connection,
    *,
    identity_key: str,
    title: str,
    url: str,
    published_date: str | None,
    source_note: str | None,
    content_sha256: str,
    document_type: str,
) -> None:
    connection.execute(
        """
        INSERT INTO evidence_sources(
            identity_key, title, institution, url, evidence_grade,
            published_date, retrieved_date, source_note,
            created_at, updated_at, document_type,
            content_sha256, applicable_year
        ) VALUES (?, ?, '测试机构', ?, 'official', ?, '2026-08-13', ?,
                  '2026-08-13T00:00:00+08:00',
                  '2026-08-13T00:00:00+08:00', ?, ?, 2026)
        """,
        (
            identity_key,
            title,
            url,
            published_date,
            source_note,
            document_type,
            content_sha256,
        ),
    )


def _insert_branch(
    connection: sqlite3.Connection,
    root: sqlite3.Row,
    fingerprint: str,
    *,
    source_hash: str | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO evidence_source_metadata_corrections(
            correction_fingerprint, source_id, source_content_sha256,
            field_name, prior_effective_value, corrected_value,
            supersedes_correction_id, basis_url,
            basis_content_sha256, basis_retrieved_date, reason,
            trace_id, created_at
        ) VALUES (?, ?, ?, 'published_date', ?, '2025-09-28', ?,
                  'https://example.edu/branch', ?, '2026-08-13',
                  '非法分叉测试。', ?, '2026-08-13T11:02:00+08:00')
        """,
        (
            fingerprint,
            root["source_id"],
            source_hash or root["source_content_sha256"],
            root["corrected_value"],
            root["id"],
            "b" * 64,
            str(uuid.uuid4()),
        ),
    )


if __name__ == "__main__":
    unittest.main()
