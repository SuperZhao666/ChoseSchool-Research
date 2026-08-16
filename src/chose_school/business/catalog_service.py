from __future__ import annotations

from typing import Any, Mapping, Sequence

from chose_school.business.ports import CatalogQueryStore
from chose_school.domain.models import CatalogFilter
from chose_school.domain.errors import ValidationError


class CatalogService:
    def __init__(self, query_store: CatalogQueryStore) -> None:
        self._query_store = query_store

    def get_summary(self) -> Mapping[str, Any]:
        return self._query_store.summary()

    def list_catalog(
        self, catalog_filter: CatalogFilter
    ) -> Sequence[Mapping[str, Any]]:
        if not 1 <= catalog_filter.limit <= 100_000:
            raise ValidationError("INVALID_LIMIT", "limit must be between 1 and 100000")
        return self._query_store.list_catalog(catalog_filter)

    def list_issues(
        self,
        severity: str | None = None,
        status: str = "open",
        limit: int = 100,
    ) -> Sequence[Mapping[str, Any]]:
        if severity not in {None, "info", "warning", "error"}:
            raise ValidationError("INVALID_SEVERITY", "severity must be info, warning, or error")
        if status not in {"open", "resolved", "wont_fix"}:
            raise ValidationError("INVALID_ISSUE_STATUS", "invalid issue status")
        if not 1 <= limit <= 100_000:
            raise ValidationError("INVALID_LIMIT", "limit must be between 1 and 100000")
        return self._query_store.list_issues(severity, status, limit)

    def doctor(self) -> Mapping[str, Any]:
        return self._query_store.doctor()
