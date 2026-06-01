package com.fanbook.book.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fanbook.book.domain.SegmentType;
import com.fanbook.testsupport.MinimalEpubFactory;
import org.junit.jupiter.api.Test;

class EpubParserTest {

    private final EpubParser parser = new EpubParser();

    @Test
    void parsesMinimalEpubIntoChaptersAndSegments() {
        ParsedBook book = parser.parse(MinimalEpubFactory.create());

        assertThat(book.title()).isEqualTo("Demo Book");
        assertThat(book.chapters()).hasSize(1);
        assertThat(book.chapters().getFirst().title()).isEqualTo("Chapter One");
        assertThat(book.chapters().getFirst().segments())
                .extracting(ParsedSegment::sourceText)
                .containsExactly("Chapter One", "Hello world.", "Alice went to Wonderland.");
        assertThat(book.chapters().getFirst().segments().getFirst().segmentType()).isEqualTo(SegmentType.TITLE);
    }

    @Test
    void rejectsInvalidArchive() {
        assertThatThrownBy(() -> parser.parse("not epub".getBytes()))
                .isInstanceOf(EpubParserException.class)
                .hasMessageContaining("valid EPUB archive");
    }
}
