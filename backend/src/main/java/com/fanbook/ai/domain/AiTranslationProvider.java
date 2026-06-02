package com.fanbook.ai.domain;

public interface AiTranslationProvider {
    String name();

    StructuredTranslationResult translateChunk(StructuredTranslationRequest request);
}
