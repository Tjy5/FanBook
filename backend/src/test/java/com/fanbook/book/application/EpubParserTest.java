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
    void capturesInlineMarkupPlaceholderMetadataForSupportedInlineElements() {
        ParsedBook book = parser.parse(MinimalEpubFactory.create("""
                <h1>Chapter One</h1>
                <p>Hello <em>bright</em> <strong>world</strong> and <a href="https://example.test">Alice</a>.</p>
                """));

        ParsedSegment paragraph = book.chapters().getFirst().segments().get(1);

        assertThat(paragraph.sourceText()).isEqualTo("Hello bright world and Alice.");
        assertThat(paragraph.locatorJson()).contains("\"sourceTemplate\"");
        assertThat(paragraph.locatorJson()).contains("[id0]bright[id1]");
        assertThat(paragraph.locatorJson()).contains("\"tagName\":\"em\"");
        assertThat(paragraph.locatorJson()).contains("\"tagName\":\"strong\"");
        assertThat(paragraph.locatorJson()).contains("\"href\":\"https://example.test\"");
        assertThat(SegmentInlineMarkup.locator(paragraph.locatorJson()).sourceTemplate())
                .isEqualTo("Hello [id0]bright[id1] [id2]world[id3] and [id4]Alice[id5].");
    }

    @Test
    void parsesHtmlSpineDocumentsWithHtml5VoidTags() {
        ParsedBook book = parser.parse(htmlEpub("""
                <h1>Chapter One</h1>
                <p><img src="cover.png"></p>
                <p>Hello <em>bright</em> world.</p>
                """));

        assertThat(book.title()).isEqualTo("HTML Demo");
        assertThat(book.chapters()).hasSize(1);
        assertThat(book.chapters().getFirst().sourceDocPath()).isEqualTo("chapter.html");
        assertThat(book.chapters().getFirst().segments())
                .extracting(ParsedSegment::sourceText)
                .containsExactly("Chapter One", "Hello bright world.");
        assertThat(SegmentInlineMarkup.locator(book.chapters().getFirst().segments().get(1).locatorJson()).sourceTemplate())
                .isEqualTo("Hello [id0]bright[id1] world.");
    }

    @Test
    void leavesUnsupportedBlockMarkupOnLegacyPlainTextPath() {
        ParsedBook book = parser.parse(MinimalEpubFactory.create("""
                <h1>Chapter One</h1>
                <p>Before <img alt="cover" src="cover.jpg"/> after.</p>
                """));

        ParsedSegment paragraph = book.chapters().getFirst().segments().get(1);

        assertThat(paragraph.sourceText()).isEqualTo("Before after.");
        assertThat(paragraph.locatorJson()).doesNotContain("\"sourceTemplate\"");
    }

    @Test
    void splitsLongParagraphOnPunctuationWhenSentenceBoundariesAreTooLarge() {
        String longClause = "word ".repeat(250).trim();
        String paragraph = longClause + ", " + longClause + ", " + longClause;

        ParsedBook book = parser.parse(MinimalEpubFactory.create("""
                <h1>Chapter One</h1>
                <p>%s</p>
                """.formatted(paragraph)));

        List<ParsedSegment> paragraphParts = book.chapters().getFirst().segments().stream()
                .filter(segment -> segment.segmentType() == SegmentType.PARAGRAPH)
                .toList();
        assertThat(paragraphParts).hasSize(3);
        assertThat(String.join(" ", paragraphParts.stream().map(ParsedSegment::sourceText).toList()))
                .isEqualTo(paragraph);
    }

    @Test
    void splitsLongParagraphOnNewlineWhenPunctuationIsUnavailable() {
        String line = "word ".repeat(250).trim();
        String paragraph = line + "\n" + line + "\n" + line;

        ParsedBook book = parser.parse(MinimalEpubFactory.create("""
                <h1>Chapter One</h1>
                <p>%s</p>
                """.formatted(paragraph)));

        List<ParsedSegment> paragraphParts = book.chapters().getFirst().segments().stream()
                .filter(segment -> segment.segmentType() == SegmentType.PARAGRAPH)
                .toList();
        assertThat(paragraphParts).hasSize(3);
        assertThat(String.join(" ", paragraphParts.stream().map(ParsedSegment::sourceText).toList()))
                .isEqualTo(SegmentInlineMarkup.normalizeSegmentText(paragraph));
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

    private static byte[] htmlEpub(String bodyContent) {
        try {
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            try (ZipOutputStream zip = new ZipOutputStream(output, StandardCharsets.UTF_8)) {
                entry(zip, "META-INF/container.xml", """
                        <?xml version="1.0" encoding="UTF-8"?>
                        <container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
                          <rootfiles>
                            <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
                          </rootfiles>
                        </container>
                        """);
                entry(zip, "content.opf", """
                        <?xml version="1.0" encoding="UTF-8"?>
                        <package version="2.0" xmlns="http://www.idpf.org/2007/opf">
                          <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
                            <dc:title>HTML Demo</dc:title>
                          </metadata>
                          <manifest>
                            <item id="chapter" href="chapter.html" media-type="text/html"/>
                          </manifest>
                          <spine>
                            <itemref idref="chapter"/>
                          </spine>
                        </package>
                        """);
                entry(zip, "chapter.html", """
                        <!DOCTYPE html>
                        <html>
                          <head>
                            <meta charset="UTF-8">
                            <link href="book.css" rel="stylesheet" type="text/css">
                          </head>
                          <body>
                            %s
                          </body>
                        </html>
                        """.formatted(bodyContent));
            }
            return output.toByteArray();
        } catch (Exception exception) {
            throw new IllegalStateException(exception);
        }
    }

    private static void entry(ZipOutputStream zip, String name, String content) throws Exception {
        zip.putNextEntry(new ZipEntry(name));
        zip.write(content.getBytes(StandardCharsets.UTF_8));
        zip.closeEntry();
    }

    private static String longParagraph() {
        return "This sentence gives the parser a natural boundary for semantic splitting. ".repeat(80).trim();
    }
}
