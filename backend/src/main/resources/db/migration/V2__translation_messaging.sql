CREATE TABLE active_translation_sessions (
    book_id BIGINT NOT NULL,
    job_id BIGINT NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (book_id),
    CONSTRAINT fk_active_session_book FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    CONSTRAINT fk_active_session_job FOREIGN KEY (job_id) REFERENCES translation_jobs(id) ON DELETE CASCADE
);

ALTER TABLE translation_chunks
    ADD COLUMN locked_until DATETIME(6);

ALTER TABLE translation_chunks
    ADD COLUMN worker_id VARCHAR(64);

CREATE INDEX idx_chunk_status_lease ON translation_chunks(status, locked_until);
CREATE INDEX idx_active_session_job ON active_translation_sessions(job_id);
