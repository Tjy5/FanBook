package com.fanbook.export.domain;

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
@Table(name = "export_artifacts")
public class ExportArtifactEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "book_id", nullable = false)
    private BookEntity book;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 64)
    private ExportArtifactKind kind;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private ExportArtifactStatus status;

    @Column(name = "object_key", columnDefinition = "LONGTEXT")
    private String objectKey;

    @Column(nullable = false, columnDefinition = "LONGTEXT")
    private String filename;

    @Column(name = "size_bytes")
    private Long sizeBytes;

    @Column(length = 128)
    private String checksum;

    @Column(name = "created_at", nullable = false, insertable = false, updatable = false, columnDefinition = "DATETIME(6)")
    private OffsetDateTime createdAt;

    protected ExportArtifactEntity() {
    }

    public ExportArtifactEntity(BookEntity book, ExportArtifactKind kind, ExportArtifactStatus status, String filename) {
        this.book = book;
        this.kind = kind;
        this.status = status;
        this.filename = filename;
    }

    public Long getId() {
        return id;
    }

    public BookEntity getBook() {
        return book;
    }

    public ExportArtifactKind getKind() {
        return kind;
    }

    public ExportArtifactStatus getStatus() {
        return status;
    }

    public String getObjectKey() {
        return objectKey;
    }

    public String getFilename() {
        return filename;
    }

    public Long getSizeBytes() {
        return sizeBytes;
    }

    public String getChecksum() {
        return checksum;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public void markReady(String objectKey, long sizeBytes, String checksum) {
        this.status = ExportArtifactStatus.READY;
        this.objectKey = objectKey;
        this.sizeBytes = sizeBytes;
        this.checksum = checksum;
    }

    public void markFailed() {
        this.status = ExportArtifactStatus.FAILED;
    }
}
