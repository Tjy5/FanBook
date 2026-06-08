package com.fanbook.translation.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.fanbook.ai.domain.StructuredTranslationGlossaryItem;
import java.util.List;
import org.junit.jupiter.api.Test;

class TranslationGlossaryBuilderTest {

    private final TranslationGlossaryBuilder builder = new TranslationGlossaryBuilder();

    @Test
    void includesConfiguredTermsWhenAutoCandidateLimitIsZero() {
        StructuredTranslationGlossaryItem alice = new StructuredTranslationGlossaryItem(
                "Alice",
                "艾丽丝",
                "person",
                "Use this name consistently."
        );

        List<StructuredTranslationGlossaryItem> glossary = builder.build(
                List.of(alice),
                List.of("Alice went to Wonderland."),
                0
        );

        assertThat(glossary).containsExactly(alice);
    }

    @Test
    void autoCandidateLimitIgnoresConfiguredTermDuplicates() {
        StructuredTranslationGlossaryItem alice = new StructuredTranslationGlossaryItem(
                "Alice",
                "艾丽丝",
                "person",
                "Use this name consistently."
        );

        List<StructuredTranslationGlossaryItem> glossary = builder.build(
                List.of(alice),
                List.of("Alice met Wonderland near Cheshire Cat."),
                1
        );

        assertThat(glossary)
                .extracting(StructuredTranslationGlossaryItem::sourceTerm)
                .containsExactly("Alice", "Wonderland");
    }
}
