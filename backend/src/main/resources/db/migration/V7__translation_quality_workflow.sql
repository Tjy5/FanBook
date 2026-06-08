CREATE TABLE translation_rule_snapshots (
    id BIGINT NOT NULL AUTO_INCREMENT,
    book_id BIGINT NOT NULL,
    snapshot_hash VARCHAR(64) NOT NULL,
    target_language VARCHAR(16) NOT NULL,
    prompt_profile_json LONGTEXT NOT NULL,
    glossary_json LONGTEXT NOT NULL,
    preservation_json LONGTEXT NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    CONSTRAINT fk_translation_rule_snapshots_book FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE INDEX idx_translation_rule_snapshot_book ON translation_rule_snapshots(book_id);
CREATE INDEX idx_translation_rule_snapshot_hash ON translation_rule_snapshots(snapshot_hash);

ALTER TABLE translation_jobs
    ADD COLUMN rule_snapshot_id BIGINT;

ALTER TABLE translation_jobs
    ADD CONSTRAINT fk_translation_jobs_rule_snapshot FOREIGN KEY (rule_snapshot_id) REFERENCES translation_rule_snapshots(id) ON DELETE SET NULL;

CREATE INDEX idx_translation_jobs_rule_snapshot ON translation_jobs(rule_snapshot_id);

CREATE TABLE translation_glossary_candidates (
    id BIGINT NOT NULL AUTO_INCREMENT,
    book_id BIGINT NOT NULL,
    source_term LONGTEXT NOT NULL,
    source_norm VARCHAR(512) NOT NULL,
    target_term LONGTEXT,
    category VARCHAR(64),
    note LONGTEXT,
    status VARCHAR(32) NOT NULL,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    first_segment_id BIGINT,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    CONSTRAINT fk_translation_glossary_candidates_book FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    CONSTRAINT fk_translation_glossary_candidates_segment FOREIGN KEY (first_segment_id) REFERENCES segments(id) ON DELETE SET NULL
);

CREATE INDEX idx_translation_glossary_candidate_book_status ON translation_glossary_candidates(book_id, status);
CREATE INDEX idx_translation_glossary_candidate_book_source ON translation_glossary_candidates(book_id, source_norm);

ALTER TABLE translation_chunks
    ADD COLUMN parent_chunk_id BIGINT;

ALTER TABLE translation_chunks
    ADD COLUMN degradation_depth INTEGER NOT NULL DEFAULT 0;

ALTER TABLE translation_chunks
    ADD CONSTRAINT fk_translation_chunks_parent FOREIGN KEY (parent_chunk_id) REFERENCES translation_chunks(id) ON DELETE SET NULL;

CREATE INDEX idx_translation_chunks_parent ON translation_chunks(parent_chunk_id);
