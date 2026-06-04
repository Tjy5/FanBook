package com.fanbook.ai.domain;

public interface AiTranslationProvider {
    String name();

    StructuredTranslationResult translateChunk(StructuredTranslationRequest request, String modelName);

    default StructuredTranslationResult translateChunk(StructuredTranslationRequest request) {
        return translateChunk(request, "");
    }
}
