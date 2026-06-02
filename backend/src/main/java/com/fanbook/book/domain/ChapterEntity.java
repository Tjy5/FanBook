package com.fanbook.book.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;

@Entity
@Table(name = "chapters")
public class ChapterEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "book_id", nullable = false)
    private BookEntity book;

    @Column(name = "chapter_order", nullable = false)
    private int chapterOrder;

    @Column(nullable = false, columnDefinition = "TEXT")
    private String title;

    @Column(name = "source_doc_path", nullable = false, columnDefinition = "TEXT")
    private String sourceDocPath;

    @Column(name = "total_segments", nullable = false)
    private int totalSegments;

    @Column(name = "translated_segments", nullable = false)
    private int translatedSegments;

    @Column(name = "failed_segments", nullable = false)
    private int failedSegments;

    @Column(name = "created_at", nullable = false, insertable = false, updatable = false, columnDefinition = "TIMESTAMP WITH TIME ZONE")
    private OffsetDateTime createdAt;

    @Column(name = "updated_at", nullable = false, insertable = false, updatable = false, columnDefinition = "TIMESTAMP WITH TIME ZONE")
    private OffsetDateTime updatedAt;

    protected ChapterEntity() {
    }

    public ChapterEntity(BookEntity book, int chapterOrder, String title, String sourceDocPath) {
        this.book = book;
        this.chapterOrder = chapterOrder;
        this.title = title;
        this.sourceDocPath = sourceDocPath;
    }

    public Long getId() {
        return id;
    }

    public BookEntity getBook() {
        return book;
    }

    public int getChapterOrder() {
        return chapterOrder;
    }

    public String getTitle() {
        return title;
    }

    public String getSourceDocPath() {
        return sourceDocPath;
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

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public OffsetDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void updateProgress(int totalSegments, int translatedSegments, int failedSegments) {
        this.totalSegments = totalSegments;
        this.translatedSegments = translatedSegments;
        this.failedSegments = failedSegments;
    }
}
