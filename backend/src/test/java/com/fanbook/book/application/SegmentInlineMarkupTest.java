package com.fanbook.book.application;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class SegmentInlineMarkupTest {

    @Test
    void validatesPlaceholderPresenceUniquenessAndOrder() {
        String locatorJson = locatorJson();

        assertThat(SegmentInlineMarkup.validateTranslatedText("你好 [id0]明亮[id1] 世界", locatorJson).valid())
                .isTrue();
        assertThat(SegmentInlineMarkup.validateTranslatedText("你好 明亮[id1] 世界", locatorJson).message())
                .contains("missing inline placeholder");
        assertThat(SegmentInlineMarkup.validateTranslatedText("你好 [id0][id0]明亮[id1] 世界", locatorJson).message())
                .contains("duplicate inline placeholder");
        assertThat(SegmentInlineMarkup.validateTranslatedText("你好 [id0]明亮[id1] [id9] 世界", locatorJson).message())
                .contains("extra inline placeholder");
        assertThat(SegmentInlineMarkup.validateTranslatedText("你好 [id1]明亮[id0] 世界", locatorJson).message())
                .contains("out of order");
    }

    @Test
    void stripsKnownPlaceholdersForDisplayText() {
        String locatorJson = locatorJson();

        assertThat(SegmentInlineMarkup.displayText("[zh] Hello [id0]bright[id1] world.", locatorJson))
                .isEqualTo("[zh] Hello bright world.");
    }

    private static String locatorJson() {
        return SegmentInlineMarkup.locatorJson(new SegmentInlineMarkup.Locator(
                "OEBPS/chapter1.xhtml",
                5,
                null,
                null,
                "Hello [id0]bright[id1] world.",
                List.of(
                        new SegmentInlineMarkup.InlinePlaceholder(
                                "[id0]",
                                SegmentInlineMarkup.InlinePlaceholderKind.OPEN.name(),
                                "em",
                                "http://www.w3.org/1999/xhtml",
                                Map.of(),
                                null,
                                "[id1]"
                        ),
                        new SegmentInlineMarkup.InlinePlaceholder(
                                "[id1]",
                                SegmentInlineMarkup.InlinePlaceholderKind.CLOSE.name(),
                                null,
                                null,
                                Map.of(),
                                "[id0]",
                                null
                        )
                )
        ));
    }
}
