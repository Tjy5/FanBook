CREATE TABLE books (
    id BIGINT NOT NULL AUTO_INCREMENT,
    filename LONGTEXT NOT NULL,
    title LONGTEXT NOT NULL,
    translated_title LONGTEXT,
    source_language VARCHAR(16) NOT NULL,
    source_object_key LONGTEXT NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id)
);

CREATE TABLE chapters (
    id BIGINT NOT NULL AUTO_INCREMENT,
    book_id BIGINT NOT NULL,
    chapter_order INTEGER NOT NULL,
    title LONGTEXT NOT NULL,
    source_doc_path LONGTEXT NOT NULL,
    total_segments INTEGER NOT NULL DEFAULT 0,
    translated_segments INTEGER NOT NULL DEFAULT 0,
    failed_segments INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    CONSTRAINT fk_chapters_book FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE TABLE segments (
    id BIGINT NOT NULL AUTO_INCREMENT,
    book_id BIGINT NOT NULL,
    chapter_id BIGINT NOT NULL,
    segment_order INTEGER NOT NULL,
    source_text LONGTEXT NOT NULL,
    translated_text LONGTEXT,
    segment_type VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    locator_json LONGTEXT NOT NULL,
    source_digest VARCHAR(64) NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_error_code VARCHAR(64),
    last_error_message LONGTEXT,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    CONSTRAINT fk_segments_book FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    CONSTRAINT fk_segments_chapter FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
);

CREATE TABLE translation_jobs (
    id BIGINT NOT NULL AUTO_INCREMENT,
    book_id BIGINT NOT NULL,
    status VARCHAR(32) NOT NULL,
    provider_name VARCHAR(64) NOT NULL,
    model_name VARCHAR(128) NOT NULL,
    total_segments INTEGER NOT NULL DEFAULT 0,
    translated_segments INTEGER NOT NULL DEFAULT 0,
    failed_segments INTEGER NOT NULL DEFAULT 0,
    progress DOUBLE NOT NULL DEFAULT 0,
    requested_by VARCHAR(128),
    started_at DATETIME(6),
    finished_at DATETIME(6),
    error_summary LONGTEXT,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    CONSTRAINT fk_translation_jobs_book FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE TABLE translation_chunks (
    id BIGINT NOT NULL AUTO_INCREMENT,
    job_id BIGINT NOT NULL,
    book_id BIGINT NOT NULL,
    chapter_id BIGINT NOT NULL,
    chunk_order INTEGER NOT NULL,
    segment_ids_json LONGTEXT NOT NULL,
    status VARCHAR(32) NOT NULL,
    estimated_tokens INTEGER NOT NULL DEFAULT 0,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error_code VARCHAR(64),
    last_error_message LONGTEXT,
    started_at DATETIME(6),
    finished_at DATETIME(6),
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    CONSTRAINT fk_translation_chunks_job FOREIGN KEY (job_id) REFERENCES translation_jobs(id) ON DELETE CASCADE,
    CONSTRAINT fk_translation_chunks_book FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    CONSTRAINT fk_translation_chunks_chapter FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
);

CREATE TABLE export_artifacts (
    id BIGINT NOT NULL AUTO_INCREMENT,
    book_id BIGINT NOT NULL,
    kind VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    object_key LONGTEXT,
    filename LONGTEXT NOT NULL,
    size_bytes BIGINT,
    checksum VARCHAR(128),
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    CONSTRAINT fk_export_artifacts_book FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE INDEX idx_chapter_book_order ON chapters(book_id, chapter_order);
CREATE INDEX idx_segment_chapter_order ON segments(chapter_id, segment_order);
CREATE INDEX idx_segment_book_status ON segments(book_id, status);
CREATE INDEX idx_job_book_updated ON translation_jobs(book_id, updated_at DESC);
CREATE INDEX idx_chunk_job_status ON translation_chunks(job_id, status);
CREATE INDEX idx_artifact_book_kind ON export_artifacts(book_id, kind);
