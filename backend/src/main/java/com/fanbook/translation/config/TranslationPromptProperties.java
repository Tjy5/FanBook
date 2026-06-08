package com.fanbook.translation.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "fanbook.translation.prompt")
public record TranslationPromptProperties(
        String name,
        String version,
        String styleInstruction,
        String translationInstruction,
        String reviewInstruction,
        String analysisInstruction,
        boolean preserveFormatting
) {
    public TranslationPromptProperties {
        name = value(name, "default");
        version = value(version, "v1");
        styleInstruction = value(styleInstruction, "");
        translationInstruction = value(translationInstruction, "");
        reviewInstruction = value(reviewInstruction, "");
        analysisInstruction = value(analysisInstruction, "");
    }

    private static String value(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value.trim();
    }
}
