package com.fanbook.translation.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;

@Entity
@Table(name = "translation_cache")
public class TranslationCacheEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "cache_key", nullable = false, length = 64, unique = true, columnDefinition = "CHAR(64)")
    private String cacheKey;

    @Column(name = "source_digest", nullable = false, length = 64, columnDefinition = "CHAR(64)")
    private String sourceDigest;

    @Column(name = "source_language", nullable = false, length = 16)
    private String sourceLanguage;

    @Column(name = "target_language", nullable = false, length = 16)
    private String targetLanguage;

    @Column(name = "provider_name", nullable = false, length = 64)
    private String providerName;

    @Column(name = "model_name", nullable = false, length = 128)
    private String modelName;

    @Column(name = "prompt_version", nullable = false, length = 32)
    private String promptVersion;

    @Column(name = "translated_text", nullable = false, columnDefinition = "LONGTEXT")
    private String translatedText;

    @Column(name = "hit_count", nullable = false)
    private int hitCount;

    @Column(name = "last_used_at", columnDefinition = "DATETIME(6)")
    private OffsetDateTime lastUsedAt;

    @Column(name = "created_at", nullable = false, insertable = false, updatable = false, columnDefinition = "DATETIME(6)")
    private OffsetDateTime createdAt;

    @Column(name = "updated_at", nullable = false, insertable = false, updatable = false, columnDefinition = "DATETIME(6)")
    private OffsetDateTime updatedAt;

    protected TranslationCacheEntity() {
    }

    public TranslationCacheEntity(
            String cacheKey,
            String sourceDigest,
            String sourceLanguage,
            String targetLanguage,
            String providerName,
            String modelName,
            String promptVersion,
            String translatedText
    ) {
        this.cacheKey = cacheKey;
        this.sourceDigest = sourceDigest;
        this.sourceLanguage = sourceLanguage;
        this.targetLanguage = targetLanguage;
        this.providerName = providerName;
        this.modelName = modelName;
        this.promptVersion = promptVersion;
        this.translatedText = translatedText;
    }

    public Long getId() {
        return id;
    }

    public String getCacheKey() {
        return cacheKey;
    }

    public String getSourceDigest() {
        return sourceDigest;
    }

    public String getSourceLanguage() {
        return sourceLanguage;
    }

    public String getTargetLanguage() {
        return targetLanguage;
    }

    public String getProviderName() {
        return providerName;
    }

    public String getModelName() {
        return modelName;
    }

    public String getPromptVersion() {
        return promptVersion;
    }

    public String getTranslatedText() {
        return translatedText;
    }

    public int getHitCount() {
        return hitCount;
    }

    public OffsetDateTime getLastUsedAt() {
        return lastUsedAt;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public OffsetDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void markUsed(OffsetDateTime lastUsedAt) {
        this.hitCount++;
        this.lastUsedAt = lastUsedAt;
    }
}
