package com.fanbook.translation.domain;

import com.fanbook.book.domain.BookEntity;
import com.fanbook.book.domain.SegmentEntity;
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
@Table(name = "translation_glossary_candidates")
public class TranslationGlossaryCandidateEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "book_id", nullable = false)
    private BookEntity book;

    @Column(name = "source_term", nullable = false, columnDefinition = "LONGTEXT")
    private String sourceTerm;

    @Column(name = "source_norm", nullable = false, length = 512)
    private String sourceNorm;

    @Column(name = "target_term", columnDefinition = "LONGTEXT")
    private String targetTerm;

    @Column(length = 64)
    private String category;

    @Column(columnDefinition = "LONGTEXT")
    private String note;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private TranslationGlossaryCandidateStatus status;

    @Column(name = "evidence_count", nullable = false)
    private int evidenceCount;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "first_segment_id")
    private SegmentEntity firstSegment;

    @Column(name = "created_at", nullable = false, insertable = false, updatable = false, columnDefinition = "DATETIME(6)")
    private OffsetDateTime createdAt;

    @Column(name = "updated_at", nullable = false, insertable = false, updatable = false, columnDefinition = "DATETIME(6)")
    private OffsetDateTime updatedAt;

    protected TranslationGlossaryCandidateEntity() {
    }

    public TranslationGlossaryCandidateEntity(
            BookEntity book,
            String sourceTerm,
            String sourceNorm,
            String targetTerm,
            String category,
            String note,
            TranslationGlossaryCandidateStatus status,
            int evidenceCount,
            SegmentEntity firstSegment
    ) {
        this.book = book;
        this.sourceTerm = sourceTerm;
        this.sourceNorm = sourceNorm;
        this.targetTerm = targetTerm;
        this.category = category;
        this.note = note;
        this.status = status;
        this.evidenceCount = evidenceCount;
        this.firstSegment = firstSegment;
    }

    public Long getId() {
        return id;
    }

    public BookEntity getBook() {
        return book;
    }

    public String getSourceTerm() {
        return sourceTerm;
    }

    public String getSourceNorm() {
        return sourceNorm;
    }

    public String getTargetTerm() {
        return targetTerm;
    }

    public String getCategory() {
        return category;
    }

    public String getNote() {
        return note;
    }

    public TranslationGlossaryCandidateStatus getStatus() {
        return status;
    }

    public int getEvidenceCount() {
        return evidenceCount;
    }

    public SegmentEntity getFirstSegment() {
        return firstSegment;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public OffsetDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void mergeEvidence(String targetTerm, String category, String note, SegmentEntity firstSegment) {
        this.evidenceCount++;
        if (isBlank(this.targetTerm) && !isBlank(targetTerm)) {
            this.targetTerm = targetTerm.trim();
        }
        if (isBlank(this.category) && !isBlank(category)) {
            this.category = category.trim();
        }
        if (isBlank(this.note) && !isBlank(note)) {
            this.note = note.trim();
        }
        if (this.firstSegment == null) {
            this.firstSegment = firstSegment;
        }
    }

    public void markAccepted() {
        this.status = TranslationGlossaryCandidateStatus.ACCEPTED;
    }

    public void markRejected() {
        this.status = TranslationGlossaryCandidateStatus.REJECTED;
    }

    public void markConflict() {
        this.status = TranslationGlossaryCandidateStatus.CONFLICT;
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}
