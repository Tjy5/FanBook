package com.fanbook.translation.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;

@Entity
@Table(name = "active_translation_sessions")
public class ActiveTranslationSessionEntity {

    @Id
    @Column(name = "book_id")
    private Long bookId;

    @Column(name = "job_id", nullable = false)
    private Long jobId;

    @Column(name = "created_at", nullable = false, insertable = false, updatable = false, columnDefinition = "DATETIME(6)")
    private OffsetDateTime createdAt;

    protected ActiveTranslationSessionEntity() {
    }

    public ActiveTranslationSessionEntity(Long bookId, Long jobId) {
        this.bookId = bookId;
        this.jobId = jobId;
    }

    public Long getBookId() {
        return bookId;
    }

    public Long getJobId() {
        return jobId;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }
}
