package com.fanbook.translation.application;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class TranslationTextProtectorTest {

    private final TranslationTextProtector protector = new TranslationTextProtector();

    @Test
    void detectsMissingTechnicalMeasurementsAndIdentifiers() {
        var missing = protector.missingPreservedTokens(
                "Set CPU_A17 to 3.5GHz and keep image.asset.v2 unchanged.",
                "设置处理器到 3.5 并保持资源不变。",
                TranslationPreservationOptions.defaults()
        );

        assertThat(missing).contains("CPU_A17", "3.5GHz", "image.asset.v2");
    }

    @Test
    void detectsMissingCodeAndFormulaSpans() {
        var missing = protector.missingPreservedTokens(
                "Use `renderBook()` and $E=mc^2$ before \\frac{a}{b}.",
                "使用函数和公式。",
                TranslationPreservationOptions.defaults()
        );

        assertThat(missing).contains("`renderBook()`", "$E=mc^2$", "\\frac{a}");
    }
}
