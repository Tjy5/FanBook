package com.fanbook.book.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;

@Entity
@Table(name = "books")
public class BookEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, columnDefinition = "TEXT")
    private String filename;

    @Column(nullable = false, columnDefinition = "TEXT")
    private String title;

    @Column(name = "translated_title", columnDefinition = "TEXT")
    private String translatedTitle;

    @Column(name = "source_language", nullable = false, length = 16)
    private String sourceLanguage;

    @Column(name = "source_object_key", nullable = false, columnDefinition = "TEXT")
    private String sourceObjectKey;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private BookStatus status;

    @Column(name = "created_at", nullable = false, insertable = false, updatable = false, columnDefinition = "TIMESTAMP WITH TIME ZONE")
    private OffsetDateTime createdAt;

    @Column(name = "updated_at", nullable = false, insertable = false, updatable = false, columnDefinition = "TIMESTAMP WITH TIME ZONE")
    private OffsetDateTime updatedAt;

    protected BookEntity() {
    }

    public BookEntity(String filename, String title, String sourceLanguage, String sourceObjectKey, BookStatus status) {
        this.filename = filename;
        this.title = title;
        this.sourceLanguage = sourceLanguage;
        this.sourceObjectKey = sourceObjectKey;
        this.status = status;
    }

    public Long getId() {
        return id;
    }

    public String getFilename() {
        return filename;
    }

    public String getTitle() {
        return title;
    }

    public String getTranslatedTitle() {
        return translatedTitle;
    }

    public String getSourceLanguage() {
        return sourceLanguage;
    }

    public String getSourceObjectKey() {
        return sourceObjectKey;
    }

    public BookStatus getStatus() {
        return status;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public OffsetDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void updateTranslatedTitle(String translatedTitle) {
        this.translatedTitle = translatedTitle;
    }

    public void markStatus(BookStatus status) {
        this.status = status;
    }
}
