package com.fanbook.translation.domain;

import com.fanbook.book.domain.BookEntity;
import com.fanbook.book.domain.ChapterEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;

@Entity
@Table(name = "translation_chunks")
public class TranslationChunkEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "job_id", nullable = false)
    private TranslationJobEntity job;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "book_id", nullable = false)
    private BookEntity book;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "chapter_id", nullable = false)
    private ChapterEntity chapter;

    @Column(name = "chunk_order", nullable = false)
    private int chunkOrder;

    @Column(name = "segment_ids_json", nullable = false, columnDefinition = "LONGTEXT")
    private String segmentIdsJson;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private TranslationChunkStatus status;

    @Column(name = "estimated_tokens", nullable = false)
    private int estimatedTokens;

    @Column(name = "attempt_count", nullable = false)
    private int attemptCount;

    @Column(name = "last_error_code", length = 64)
    private String lastErrorCode;

    @Column(name = "last_error_message", columnDefinition = "LONGTEXT")
    private String lastErrorMessage;

    @Column(name = "started_at", columnDefinition = "DATETIME(6)")
    private OffsetDateTime startedAt;

    @Column(name = "finished_at", columnDefinition = "DATETIME(6)")
    private OffsetDateTime finishedAt;

    @Column(name = "created_at", nullable = false, insertable = false, updatable = false, columnDefinition = "DATETIME(6)")
    private OffsetDateTime createdAt;

    @Column(name = "updated_at", nullable = false, insertable = false, updatable = false, columnDefinition = "DATETIME(6)")
    private OffsetDateTime updatedAt;

    protected TranslationChunkEntity() {
    }

    public TranslationChunkEntity(
            TranslationJobEntity job,
            BookEntity book,
            ChapterEntity chapter,
            int chunkOrder,
            String segmentIdsJson,
            TranslationChunkStatus status,
            int estimatedTokens
    ) {
        this.job = job;
        this.book = book;
        this.chapter = chapter;
        this.chunkOrder = chunkOrder;
        this.segmentIdsJson = segmentIdsJson;
        this.status = status;
        this.estimatedTokens = estimatedTokens;
    }

    public Long getId() {
        return id;
    }

    public TranslationJobEntity getJob() {
        return job;
    }

    public BookEntity getBook() {
        return book;
    }

    public ChapterEntity getChapter() {
        return chapter;
    }

    public int getChunkOrder() {
        return chunkOrder;
    }

    public String getSegmentIdsJson() {
        return segmentIdsJson;
    }

    public TranslationChunkStatus getStatus() {
        return status;
    }

    public int getEstimatedTokens() {
        return estimatedTokens;
    }

    public int getAttemptCount() {
        return attemptCount;
    }

    public String getLastErrorCode() {
        return lastErrorCode;
    }

    public String getLastErrorMessage() {
        return lastErrorMessage;
    }

    public OffsetDateTime getStartedAt() {
        return startedAt;
    }

    public OffsetDateTime getFinishedAt() {
        return finishedAt;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public OffsetDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void markRunning(OffsetDateTime startedAt) {
        this.status = TranslationChunkStatus.RUNNING;
        this.startedAt = startedAt;
        this.attemptCount++;
    }

    public void markPending() {
        this.status = TranslationChunkStatus.PENDING;
        this.startedAt = null;
        this.finishedAt = null;
        this.lastErrorCode = null;
        this.lastErrorMessage = null;
    }

    public void markCompleted(OffsetDateTime finishedAt) {
        this.status = TranslationChunkStatus.COMPLETED;
        this.finishedAt = finishedAt;
        this.lastErrorCode = null;
        this.lastErrorMessage = null;
    }

    public void markFailed(String lastErrorCode, String lastErrorMessage, OffsetDateTime finishedAt) {
        this.status = TranslationChunkStatus.FAILED;
        this.lastErrorCode = lastErrorCode;
        this.lastErrorMessage = lastErrorMessage;
        this.finishedAt = finishedAt;
    }
}
