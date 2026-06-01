package com.fanbook.translation.domain;

import com.fanbook.book.domain.BookEntity;
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
@Table(name = "translation_jobs")
public class TranslationJobEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "book_id", nullable = false)
    private BookEntity book;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private TranslationJobStatus status;

    @Column(name = "provider_name", nullable = false, length = 64)
    private String providerName;

    @Column(name = "model_name", nullable = false, length = 128)
    private String modelName;

    @Column(name = "total_segments", nullable = false)
    private int totalSegments;

    @Column(name = "translated_segments", nullable = false)
    private int translatedSegments;

    @Column(name = "failed_segments", nullable = false)
    private int failedSegments;

    @Column(nullable = false)
    private double progress;

    @Column(name = "requested_by", length = 128)
    private String requestedBy;

    @Column(name = "started_at", columnDefinition = "TIMESTAMP WITH TIME ZONE")
    private OffsetDateTime startedAt;

    @Column(name = "finished_at", columnDefinition = "TIMESTAMP WITH TIME ZONE")
    private OffsetDateTime finishedAt;

    @Column(name = "error_summary", columnDefinition = "TEXT")
    private String errorSummary;

    @Column(name = "created_at", nullable = false, insertable = false, updatable = false, columnDefinition = "TIMESTAMP WITH TIME ZONE")
    private OffsetDateTime createdAt;

    @Column(name = "updated_at", nullable = false, insertable = false, updatable = false, columnDefinition = "TIMESTAMP WITH TIME ZONE")
    private OffsetDateTime updatedAt;

    protected TranslationJobEntity() {
    }

    public TranslationJobEntity(
            BookEntity book,
            TranslationJobStatus status,
            String providerName,
            String modelName,
            String requestedBy
    ) {
        this.book = book;
        this.status = status;
        this.providerName = providerName;
        this.modelName = modelName;
        this.requestedBy = requestedBy;
    }

    public Long getId() {
        return id;
    }

    public BookEntity getBook() {
        return book;
    }

    public TranslationJobStatus getStatus() {
        return status;
    }

    public String getProviderName() {
        return providerName;
    }

    public String getModelName() {
        return modelName;
    }

    public int getTotalSegments() {
        return totalSegments;
    }

    public int getTranslatedSegments() {
        return translatedSegments;
    }

    public int getFailedSegments() {
        return failedSegments;
    }

    public double getProgress() {
        return progress;
    }

    public String getRequestedBy() {
        return requestedBy;
    }

    public OffsetDateTime getStartedAt() {
        return startedAt;
    }

    public OffsetDateTime getFinishedAt() {
        return finishedAt;
    }

    public String getErrorSummary() {
        return errorSummary;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public OffsetDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void markRunning(OffsetDateTime startedAt) {
        this.status = TranslationJobStatus.RUNNING;
        this.startedAt = startedAt;
    }

    public void updateProgress(int totalSegments, int translatedSegments, int failedSegments, double progress) {
        this.totalSegments = totalSegments;
        this.translatedSegments = translatedSegments;
        this.failedSegments = failedSegments;
        this.progress = progress;
    }

    public void markCompleted(OffsetDateTime finishedAt) {
        this.status = TranslationJobStatus.COMPLETED;
        this.finishedAt = finishedAt;
        this.progress = 1.0;
    }

    public void markFailed(String errorSummary, OffsetDateTime finishedAt) {
        this.status = TranslationJobStatus.FAILED;
        this.errorSummary = errorSummary;
        this.finishedAt = finishedAt;
    }
}
