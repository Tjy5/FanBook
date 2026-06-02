package com.fanbook.ai.application;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fanbook.ai.domain.StructuredTranslationItem;
import com.fanbook.ai.domain.StructuredTranslationResult;
import com.fanbook.common.error.FanbookException;
import java.util.List;
import org.junit.jupiter.api.Test;

class StructuredTranslationValidatorTest {

    private final StructuredTranslationValidator validator = new StructuredTranslationValidator();

    @Test
    void rejectsMissingSegmentResult() {
        StructuredTranslationResult result = new StructuredTranslationResult(
                List.of(new StructuredTranslationItem(1L, "译文")),
                "mock",
                "mock-translator"
        );

        assertThatThrownBy(() -> validator.validate(List.of(1L, 2L), result))
                .isInstanceOf(FanbookException.class)
                .hasMessageContaining("missing segment");
    }

    @Test
    void rejectsDuplicateSegmentResult() {
        StructuredTranslationResult result = new StructuredTranslationResult(
                List.of(new StructuredTranslationItem(1L, "甲"), new StructuredTranslationItem(1L, "乙")),
                "mock",
                "mock-translator"
        );

        assertThatThrownBy(() -> validator.validate(List.of(1L), result))
                .isInstanceOf(FanbookException.class)
                .hasMessageContaining("duplicate segment");
    }
}
