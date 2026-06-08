package com.fanbook.ai.domain;

public record TranslationPromptProfile(
        String name,
        String version,
        String styleInstruction,
        String translationInstruction,
        String reviewInstruction,
        String analysisInstruction,
        boolean preserveFormatting
) {
    public TranslationPromptProfile {
        name = value(name, "default");
        version = value(version, "v1");
        styleInstruction = value(styleInstruction, "");
        translationInstruction = value(translationInstruction, "");
        reviewInstruction = value(reviewInstruction, "");
        analysisInstruction = value(analysisInstruction, "");
    }

    public static TranslationPromptProfile defaults() {
        return new TranslationPromptProfile(
                "default",
                "v1",
                "",
                "",
                "",
                "",
                true
        );
    }

    private static String value(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value.trim();
    }
}
