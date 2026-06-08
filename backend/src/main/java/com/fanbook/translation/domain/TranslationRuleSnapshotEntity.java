package com.fanbook.translation.domain;

import com.fanbook.book.domain.BookEntity;
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
@Table(name = "translation_rule_snapshots")
public class TranslationRuleSnapshotEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "book_id", nullable = false)
    private BookEntity book;

    @Column(name = "snapshot_hash", nullable = false, length = 64)
    private String snapshotHash;

    @Column(name = "target_language", nullable = false, length = 16)
    private String targetLanguage;

    @Column(name = "prompt_profile_json", nullable = false, columnDefinition = "LONGTEXT")
    private String promptProfileJson;

    @Column(name = "glossary_json", nullable = false, columnDefinition = "LONGTEXT")
    private String glossaryJson;

    @Column(name = "preservation_json", nullable = false, columnDefinition = "LONGTEXT")
    private String preservationJson;

    @Column(name = "created_at", nullable = false, insertable = false, updatable = false, columnDefinition = "DATETIME(6)")
    private OffsetDateTime createdAt;

    protected TranslationRuleSnapshotEntity() {
    }

    public TranslationRuleSnapshotEntity(
            BookEntity book,
            String snapshotHash,
            String targetLanguage,
            String promptProfileJson,
            String glossaryJson,
            String preservationJson
    ) {
        this.book = book;
        this.snapshotHash = snapshotHash;
        this.targetLanguage = targetLanguage;
        this.promptProfileJson = promptProfileJson;
        this.glossaryJson = glossaryJson;
        this.preservationJson = preservationJson;
    }

    public Long getId() {
        return id;
    }

    public BookEntity getBook() {
        return book;
    }

    public String getSnapshotHash() {
        return snapshotHash;
    }

    public String getTargetLanguage() {
        return targetLanguage;
    }

    public String getPromptProfileJson() {
        return promptProfileJson;
    }

    public String getGlossaryJson() {
        return glossaryJson;
    }

    public String getPreservationJson() {
        return preservationJson;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }
}
