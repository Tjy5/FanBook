CREATE TABLE translation_cache (
    id BIGINT NOT NULL AUTO_INCREMENT,
    cache_key CHAR(64) NOT NULL,
    source_digest CHAR(64) NOT NULL,
    source_language VARCHAR(16) NOT NULL,
    target_language VARCHAR(16) NOT NULL,
    provider_name VARCHAR(64) NOT NULL,
    model_name VARCHAR(128) NOT NULL,
    prompt_version VARCHAR(32) NOT NULL DEFAULT 'v1',
    translated_text LONGTEXT NOT NULL,
    hit_count INTEGER NOT NULL DEFAULT 0,
    last_used_at DATETIME(6),
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    CONSTRAINT uk_translation_cache_key UNIQUE (cache_key)
);

CREATE INDEX idx_translation_cache_source_digest ON translation_cache(source_digest);
CREATE INDEX idx_translation_cache_last_used ON translation_cache(last_used_at);
