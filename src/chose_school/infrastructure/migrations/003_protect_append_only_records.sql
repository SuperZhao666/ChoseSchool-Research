CREATE TRIGGER protect_raw_catalog_rows_update
BEFORE UPDATE ON raw_catalog_rows
BEGIN
    SELECT RAISE(ABORT, 'raw_catalog_rows are immutable');
END;

CREATE TRIGGER protect_raw_catalog_rows_delete
BEFORE DELETE ON raw_catalog_rows
BEGIN
    SELECT RAISE(ABORT, 'raw_catalog_rows are immutable');
END;

CREATE TRIGGER protect_project_observations_update
BEFORE UPDATE ON project_year_observations
BEGIN
    SELECT RAISE(ABORT, 'project_year_observations are append-only');
END;

CREATE TRIGGER protect_project_observations_delete
BEFORE DELETE ON project_year_observations
BEGIN
    SELECT RAISE(ABORT, 'project_year_observations are append-only');
END;

CREATE TRIGGER protect_subject_verifications_update
BEFORE UPDATE ON subject_verifications
BEGIN
    SELECT RAISE(ABORT, 'subject_verifications are append-only');
END;

CREATE TRIGGER protect_subject_verifications_delete
BEFORE DELETE ON subject_verifications
BEGIN
    SELECT RAISE(ABORT, 'subject_verifications are append-only');
END;

CREATE TRIGGER protect_audit_events_update
BEFORE UPDATE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events are append-only');
END;

CREATE TRIGGER protect_audit_events_delete
BEFORE DELETE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events are append-only');
END;
