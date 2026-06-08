package com.fanbook.book.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fanbook.book.domain.SegmentType;
import com.fanbook.testsupport.MinimalEpubFactory;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import org.junit.jupiter.api.Test;
import org.springframework.util.unit.DataSize;

class EpubParserTest {

    private final EpubParser parser = new EpubParser(new EpubParserProperties(1000, DataSize.ofMegabytes(100), DataSize.ofMegabytes(25)));

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
    void skipsClearlyNonTranslatableFragments() {
        ParsedBook book = parser.parse(MinimalEpubFactory.create("""
                <h1>Chapter One</h1>
                <p>12345</p>
                <p>www.example.com</p>
                <p>...</p>
                <p>…</p>
                <p>—</p>
                <p>1.</p>
                <p>Alice stayed.</p>
                """));

        assertThat(book.chapters().getFirst().segments())
                .extracting(ParsedSegment::sourceText)
                .containsExactly("Chapter One", "Alice stayed.");
    }

    @Test
    void classifiesQuoteAndPoetrySegments() {
        ParsedBook book = parser.parse(MinimalEpubFactory.create("""
                <h1>Chapter One</h1>
                <blockquote><p>The quoted warning.</p></blockquote>
                <p class="poetry">The moon was a silver coin.</p>
                <pre>The old song returns.</pre>
                """));

        assertThat(book.chapters().getFirst().segments())
                .extracting(ParsedSegment::segmentType)
                .containsExactly(SegmentType.TITLE, SegmentType.QUOTE, SegmentType.POETRY, SegmentType.POETRY);
    }

    @Test
    void splitsLongParagraphOnSentenceBoundariesWithSharedLocatorParts() {
        String longParagraph = longParagraph();

        ParsedBook book = parser.parse(MinimalEpubFactory.create("""
                <h1>Chapter One</h1>
                <p>%s</p>
                """.formatted(longParagraph)));

        List<ParsedSegment> paragraphParts = book.chapters().getFirst().segments().stream()
                .filter(segment -> segment.segmentType() == SegmentType.PARAGRAPH)
                .toList();
        assertThat(paragraphParts).hasSizeGreaterThan(1);
        assertThat(String.join(" ", paragraphParts.stream().map(ParsedSegment::sourceText).toList()))
                .isEqualTo(longParagraph);
        assertThat(paragraphParts.getFirst().locatorJson()).contains("\"partIndex\":0");
        assertThat(paragraphParts.getFirst().locatorJson()).contains("\"partCount\":" + paragraphParts.size());
    }

    @Test
    void rejectsInvalidArchive() {
        assertThatThrownBy(() -> parser.parse("not epub".getBytes()))
                .isInstanceOf(EpubParserException.class)
                .hasMessageContaining("valid EPUB archive");
    }

    @Test
    void rejectsArchiveWithTooManyEntries() {
        EpubParser limitedParser = new EpubParser(new EpubParserProperties(1, DataSize.ofMegabytes(100), DataSize.ofMegabytes(25)));

        assertThatThrownBy(() -> limitedParser.parse(MinimalEpubFactory.create()))
                .isInstanceOf(EpubParserException.class)
                .hasMessageContaining("maximum entry count");
    }

    @Test
    void rejectsArchiveWithOversizedEntry() {
        EpubParser limitedParser = new EpubParser(new EpubParserProperties(1000, DataSize.ofMegabytes(100), DataSize.ofBytes(4)));

        assertThatThrownBy(() -> limitedParser.parse(MinimalEpubFactory.create()))
                .isInstanceOf(EpubParserException.class)
                .hasMessageContaining("maximum size");
    }

    @Test
    void rejectsUnsafeMemberPath() {
        assertThatThrownBy(() -> parser.parse(zipWith("../evil.xhtml", "oops")))
                .isInstanceOf(EpubParserException.class)
                .hasMessageContaining("unsafe member path");
    }

    private static byte[] zipWith(String name, String content) {
        try {
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            try (ZipOutputStream zip = new ZipOutputStream(output, StandardCharsets.UTF_8)) {
                zip.putNextEntry(new ZipEntry(name));
                zip.write(content.getBytes(StandardCharsets.UTF_8));
                zip.closeEntry();
            }
            return output.toByteArray();
        } catch (Exception exception) {
            throw new IllegalStateException(exception);
        }
    }

    private static String longParagraph() {
        return "This sentence gives the parser a natural boundary for semantic splitting. ".repeat(80).trim();
    }
}
