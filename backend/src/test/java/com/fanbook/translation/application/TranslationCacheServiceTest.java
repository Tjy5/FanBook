package com.fanbook.translation.application;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class TranslationCacheServiceTest {

    private final TranslationCacheService service = new TranslationCacheService(null);

    @Test
    void cacheKeyIncludesDigestLanguagesProviderModelAndPromptVersion() {
        String key1 = service.cacheKey("digest", "en", "zh", "mock", "model-a", "v1");
        String key2 = service.cacheKey("digest", "en", "zh", "mock", "model-b", "v1");

        assertThat(key1).hasSize(64);
        assertThat(key1).isNotEqualTo(key2);
    }
}
