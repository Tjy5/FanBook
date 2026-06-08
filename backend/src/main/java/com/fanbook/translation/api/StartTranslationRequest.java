package com.fanbook.translation.api;

public record StartTranslationRequest(
        String providerName,
        String modelName,
        TranslationPromptProfileRequest promptProfile
) {
    public StartTranslationRequest(String providerName, String modelName) {
        this(providerName, modelName, null);
    }

    public record TranslationPromptProfileRequest(
            String name,
            String version,
            String styleInstruction,
            String translationInstruction,
            String reviewInstruction,
            String analysisInstruction,
            Boolean preserveFormatting
    ) {
    }
}
