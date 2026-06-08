package com.fanbook.ai.domain;

import com.fanbook.translation.application.TranslationPreservationOptions;
import java.util.List;

public record StructuredGlossaryAnalysisRequest(
        String sourceLanguage,
        String targetLanguage,
        String bookTitle,
        String scopeTitle,
        TranslationPromptProfile promptProfile,
        TranslationPreservationOptions preservation,
        List<StructuredGlossaryAnalysisSourceItem> items
) {
    public StructuredGlossaryAnalysisRequest {
        promptProfile = promptProfile == null ? TranslationPromptProfile.defaults() : promptProfile;
        preservation = preservation == null ? TranslationPreservationOptions.defaults() : preservation;
        items = items == null ? List.of() : List.copyOf(items);
    }
}
