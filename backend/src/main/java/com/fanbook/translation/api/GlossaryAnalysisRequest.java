package com.fanbook.translation.api;

public record GlossaryAnalysisRequest(
        String providerName,
        String modelName,
        Integer maxSegments,
        Boolean persistCandidates,
        StartTranslationRequest.TranslationPromptProfileRequest promptProfile
) {
}
