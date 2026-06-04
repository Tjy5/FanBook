package com.fanbook.reader.domain;

import com.fanbook.book.domain.BookEntity;
import com.fanbook.book.domain.SegmentEntity;
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
@Table(name = "segment_notes")
public class SegmentNoteEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "book_id", nullable = false)
    private BookEntity book;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "segment_id", nullable = false)
    private SegmentEntity segment;

    @Column(name = "note_content", nullable = false, columnDefinition = "LONGTEXT")
    private String noteContent;

    @Column(name = "highlight_color", length = 20)
    private String highlightColor;

    @Column(name = "created_by", nullable = false, length = 64)
    private String createdBy;

    @Column(name = "created_at", nullable = false, insertable = false, updatable = false, columnDefinition = "DATETIME(6)")
    private OffsetDateTime createdAt;

    @Column(name = "updated_at", nullable = false, insertable = false, updatable = false, columnDefinition = "DATETIME(6)")
    private OffsetDateTime updatedAt;

    protected SegmentNoteEntity() {
    }

    public SegmentNoteEntity(
            BookEntity book,
            SegmentEntity segment,
            String noteContent,
            String highlightColor,
            String createdBy
    ) {
        this.book = book;
        this.segment = segment;
        this.noteContent = noteContent;
        this.highlightColor = highlightColor;
        this.createdBy = createdBy;
    }

    public Long getId() {
        return id;
    }

    public BookEntity getBook() {
        return book;
    }

    public SegmentEntity getSegment() {
        return segment;
    }

    public String getNoteContent() {
        return noteContent;
    }

    public String getHighlightColor() {
        return highlightColor;
    }

    public String getCreatedBy() {
        return createdBy;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public OffsetDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void update(String noteContent, String highlightColor) {
        this.noteContent = noteContent;
        this.highlightColor = highlightColor;
    }
}
