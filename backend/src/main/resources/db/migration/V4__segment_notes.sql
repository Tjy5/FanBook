CREATE TABLE segment_notes (
    id BIGINT NOT NULL AUTO_INCREMENT,
    book_id BIGINT NOT NULL,
    segment_id BIGINT NOT NULL,
    note_content LONGTEXT NOT NULL,
    highlight_color VARCHAR(20),
    created_by VARCHAR(64) NOT NULL DEFAULT 'local',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    CONSTRAINT fk_notes_book FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    CONSTRAINT fk_notes_segment FOREIGN KEY (segment_id) REFERENCES segments(id) ON DELETE CASCADE
);

CREATE INDEX idx_segment_notes_segment ON segment_notes(segment_id);
CREATE INDEX idx_segment_notes_book ON segment_notes(book_id);
