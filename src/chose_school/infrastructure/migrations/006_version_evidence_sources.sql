ALTER TABLE evidence_sources ADD COLUMN document_type TEXT;
ALTER TABLE evidence_sources ADD COLUMN content_sha256 TEXT;
ALTER TABLE evidence_sources ADD COLUMN applicable_year INTEGER;

CREATE INDEX ix_evidence_sources_content
    ON evidence_sources(content_sha256, applicable_year, document_type);
