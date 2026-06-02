package com.fanbook.book.domain;

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
@Table(name = "segments")
public class SegmentEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "book_id", nullable = false)
    private BookEntity book;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "chapter_id", nullable = false)
    private ChapterEntity chapter;

    @Column(name = "segment_order", nullable = false)
    private int segmentOrder;

    @Column(name = "source_text", nullable = false, columnDefinition = "TEXT")
    private String sourceText;

    @Column(name = "translated_text", columnDefinition = "TEXT")
    private String translatedText;

    @Enumerated(EnumType.STRING)
    @Column(name = "segment_type", nullable = false, length = 32)
    private SegmentType segmentType;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private SegmentStatus status;

    @Column(name = "locator_json", nullable = false, columnDefinition = "TEXT")
    private String locatorJson;

    @Column(name = "source_digest", nullable = false, length = 64)
    private String sourceDigest;

    @Column(name = "retry_count", nullable = false)
    private int retryCount;

    @Column(name = "last_error_code", length = 64)
    private String lastErrorCode;

    @Column(name = "last_error_message", columnDefinition = "TEXT")
    private String lastErrorMessage;

    @Column(name = "created_at", nullable = false, insertable = false, updatable = false, columnDefinition = "TIMESTAMP WITH TIME ZONE")
    private OffsetDateTime createdAt;

    @Column(name = "updated_at", nullable = false, insertable = false, updatable = false, columnDefinition = "TIMESTAMP WITH TIME ZONE")
    private OffsetDateTime updatedAt;

    protected SegmentEntity() {
    }

    public SegmentEntity(
            BookEntity book,
            ChapterEntity chapter,
            int segmentOrder,
            String sourceText,
            SegmentType segmentType,
            SegmentStatus status,
            String locatorJson,
            String sourceDigest
    ) {
        this.book = book;
        this.chapter = chapter;
        this.segmentOrder = segmentOrder;
        this.sourceText = sourceText;
        this.segmentType = segmentType;
        this.status = status;
        this.locatorJson = locatorJson;
        this.sourceDigest = sourceDigest;
    }

    public Long getId() {
        return id;
    }

    public BookEntity getBook() {
        return book;
    }

    public ChapterEntity getChapter() {
        return chapter;
    }

    public int getSegmentOrder() {
        return segmentOrder;
    }

    public String getSourceText() {
        return sourceText;
    }

    public String getTranslatedText() {
        return translatedText;
    }

    public SegmentType getSegmentType() {
        return segmentType;
    }

    public SegmentStatus getStatus() {
        return status;
    }

    public String getLocatorJson() {
        return locatorJson;
    }

    public String getSourceDigest() {
        return sourceDigest;
    }

    public int getRetryCount() {
        return retryCount;
    }

    public String getLastErrorCode() {
        return lastErrorCode;
    }

    public String getLastErrorMessage() {
        return lastErrorMessage;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public OffsetDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void markTranslated(String translatedText) {
        this.translatedText = translatedText;
        this.status = SegmentStatus.TRANSLATED;
        this.lastErrorCode = null;
        this.lastErrorMessage = null;
    }

    public void markFailed(String lastErrorCode, String lastErrorMessage) {
        this.status = SegmentStatus.FAILED;
        this.retryCount++;
        this.lastErrorCode = lastErrorCode;
        this.lastErrorMessage = lastErrorMessage;
    }
}
