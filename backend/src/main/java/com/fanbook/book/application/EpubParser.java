package com.fanbook.book.application;

import com.fanbook.book.domain.SegmentType;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.text.BreakIterator;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilderFactory;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.stereotype.Component;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

@Component
@EnableConfigurationProperties(EpubParserProperties.class)
public class EpubParser {

    private static final int BUFFER_SIZE = 8192;
    private static final int LONG_PARAGRAPH_TARGET_CHARACTERS = 1_800;
    private static final String URL_PATTERN = "(?i)^(https?://|www\\.).+";

    private final EpubParserProperties properties;

    public EpubParser(EpubParserProperties properties) {
        this.properties = properties;
    }

    public ParsedBook parse(byte[] content) {
        Archive archive = Archive.read(content, properties);
        Document container = xml(archive.get("META-INF/container.xml"), "META-INF/container.xml");
        String opfPath = firstAttribute(container, "rootfile", "full-path");
        if (opfPath.isBlank()) {
            throw new EpubParserException("EPUB container.xml does not define an OPF package document.");
        }

        Document opf = xml(archive.get(opfPath), opfPath);
        String title = firstText(opf, "title", "Untitled");
        String opfDir = directory(opfPath);
        List<String> spinePaths = spinePaths(opf, opfDir);
        List<ParsedChapter> chapters = new ArrayList<>();
        for (String path : spinePaths) {
            Document chapterDoc = xml(archive.get(path), path);
            List<ParsedSegment> segments = segments(path, chapterDoc);
            if (!segments.isEmpty()) {
                String chapterTitle = segments.getFirst().sourceText();
                chapters.add(new ParsedChapter(chapters.size() + 1, chapterTitle, path, segments));
            }
        }
        if (chapters.isEmpty()) {
            throw new EpubParserException("EPUB does not contain readable text segments.");
        }
        return new ParsedBook(title, List.copyOf(chapters));
    }

    private static List<String> spinePaths(Document opf, String opfDir) {
        NodeList items = opf.getElementsByTagNameNS("*", "item");
        Map<String, String> hrefById = new HashMap<>();
        for (int i = 0; i < items.getLength(); i++) {
            Element item = (Element) items.item(i);
            if ("application/xhtml+xml".equals(item.getAttribute("media-type"))) {
                hrefById.put(item.getAttribute("id"), join(opfDir, item.getAttribute("href")));
            }
        }

        NodeList refs = opf.getElementsByTagNameNS("*", "itemref");
        List<String> paths = new ArrayList<>();
        for (int i = 0; i < refs.getLength(); i++) {
            String path = hrefById.get(((Element) refs.item(i)).getAttribute("idref"));
            if (path != null) {
                paths.add(path);
            }
        }
        return paths;
    }

    private static List<ParsedSegment> segments(String docPath, Document doc) {
        List<ParsedSegment> result = new ArrayList<>();
        NodeList nodes = doc.getElementsByTagNameNS("*", "*");
        for (int i = 0; i < nodes.getLength(); i++) {
            Element element = (Element) nodes.item(i);
            String name = element.getLocalName();
            if (!List.of("h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "figcaption").contains(name)) {
                continue;
            }
            String text = element.getTextContent().trim().replaceAll("\\s+", " ");
            if (isNonTranslatable(text)) {
                continue;
            }
            SegmentType type = segmentType(element, name);
            String locator = locatorJson(docPath, i);
            List<String> parts = splitText(text, type);
            for (int partIndex = 0; partIndex < parts.size(); partIndex++) {
                String part = parts.get(partIndex);
                int order = result.size() + 1;
                String partLocator = parts.size() == 1 ? locator : locatorJson(docPath, i, partIndex, parts.size());
                result.add(new ParsedSegment(order, part, type, partLocator, sha256(part)));
            }
        }
        return result;
    }

    private static SegmentType segmentType(Element element, String name) {
        if (List.of("h1", "h2", "h3", "h4", "h5", "h6").contains(name)) {
            return SegmentType.TITLE;
        }
        if ("li".equals(name)) {
            return SegmentType.LIST_ITEM;
        }
        if ("pre".equals(name) || hasClassToken(element, "poem") || hasClassToken(element, "poetry")
                || hasClassToken(element, "verse") || hasClassToken(element, "stanza")) {
            return SegmentType.POETRY;
        }
        if (inside(element, "blockquote") || hasClassToken(element, "quote") || hasClassToken(element, "blockquote")) {
            return SegmentType.QUOTE;
        }
        if ("figcaption".equals(name)) {
            return SegmentType.IMAGE_CAPTION;
        }
        if ("p".equals(name)) {
            return SegmentType.PARAGRAPH;
        }
        return SegmentType.OTHER;
    }

    private static boolean inside(Element element, String ancestorName) {
        Node node = element.getParentNode();
        while (node instanceof Element parent) {
            if (ancestorName.equals(parent.getLocalName())) {
                return true;
            }
            node = parent.getParentNode();
        }
        return false;
    }

    private static boolean hasClassToken(Element element, String token) {
        String className = element.getAttribute("class");
        if (className == null || className.isBlank()) {
            return false;
        }
        for (String candidate : className.toLowerCase(Locale.ROOT).split("\\s+")) {
            if (candidate.equals(token) || candidate.contains("-" + token) || candidate.contains(token + "-")) {
                return true;
            }
        }
        return false;
    }

    private static List<String> splitText(String text, SegmentType type) {
        if (type != SegmentType.PARAGRAPH || text.length() <= LONG_PARAGRAPH_TARGET_CHARACTERS) {
            return List.of(text);
        }
        List<String> parts = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        for (String sentence : sentences(text)) {
            if (sentence.length() > LONG_PARAGRAPH_TARGET_CHARACTERS) {
                appendPart(parts, current);
                parts.addAll(splitByWords(sentence));
                continue;
            }
            int separator = current.isEmpty() ? 0 : 1;
            if (!current.isEmpty() && current.length() + separator + sentence.length() > LONG_PARAGRAPH_TARGET_CHARACTERS) {
                appendPart(parts, current);
            }
            if (!current.isEmpty()) {
                current.append(' ');
            }
            current.append(sentence);
        }
        appendPart(parts, current);
        if (parts.isEmpty() || !String.join(" ", parts).equals(text)) {
            return List.of(text);
        }
        return List.copyOf(parts);
    }

    private static List<String> sentences(String text) {
        BreakIterator iterator = BreakIterator.getSentenceInstance(Locale.ROOT);
        iterator.setText(text);
        List<String> result = new ArrayList<>();
        int start = iterator.first();
        for (int end = iterator.next(); end != BreakIterator.DONE; start = end, end = iterator.next()) {
            String sentence = text.substring(start, end).trim().replaceAll("\\s+", " ");
            if (!sentence.isBlank()) {
                result.add(sentence);
            }
        }
        return result.isEmpty() ? List.of(text) : result;
    }

    private static List<String> splitByWords(String text) {
        List<String> parts = new ArrayList<>();
        String remaining = text.trim();
        while (remaining.length() > LONG_PARAGRAPH_TARGET_CHARACTERS) {
            int splitAt = remaining.lastIndexOf(' ', LONG_PARAGRAPH_TARGET_CHARACTERS);
            if (splitAt < LONG_PARAGRAPH_TARGET_CHARACTERS / 2) {
                return List.of(text);
            }
            parts.add(remaining.substring(0, splitAt).trim());
            remaining = remaining.substring(splitAt).trim();
        }
        if (!remaining.isBlank()) {
            parts.add(remaining);
        }
        return parts;
    }

    private static void appendPart(List<String> parts, StringBuilder current) {
        if (!current.isEmpty()) {
            parts.add(current.toString());
            current.setLength(0);
        }
    }

    private static String locatorJson(String docPath, int index) {
        return "{\"docPath\":\"" + docPath + "\",\"index\":" + index + "}";
    }

    private static String locatorJson(String docPath, int index, int partIndex, int partCount) {
        return "{\"docPath\":\"" + docPath + "\",\"index\":" + index
                + ",\"partIndex\":" + partIndex + ",\"partCount\":" + partCount + "}";
    }

    private static boolean isNonTranslatable(String text) {
        if (text.isBlank()) {
            return true;
        }
        String compact = text.replaceAll("\\s+", "");
        if (compact.matches(URL_PATTERN)) {
            return true;
        }
        if (compact.matches("[\\p{P}\\p{S}]+")) {
            return true;
        }
        if (compact.matches("[\\p{N}]+")) {
            return true;
        }
        return compact.length() <= 3 && compact.matches("[\\p{N}\\p{P}\\p{S}]+");
    }

    private static Document xml(byte[] content, String path) {
        try {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            factory.setNamespaceAware(true);
            factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
            factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            return factory.newDocumentBuilder().parse(new ByteArrayInputStream(content));
        } catch (Exception e) {
            throw new EpubParserException("EPUB document '" + path + "' is not well-formed XML.", e);
        }
    }

    private static String firstAttribute(Document doc, String localName, String attribute) {
        NodeList nodes = doc.getElementsByTagNameNS("*", localName);
        return nodes.getLength() == 0 ? "" : ((Element) nodes.item(0)).getAttribute(attribute);
    }

    private static String firstText(Document doc, String localName, String fallback) {
        NodeList nodes = doc.getElementsByTagNameNS("*", localName);
        if (nodes.getLength() == 0) {
            return fallback;
        }
        String text = nodes.item(0).getTextContent().trim();
        return text.isBlank() ? fallback : text;
    }

    private static String directory(String path) {
        int slash = path.lastIndexOf('/');
        return slash < 0 ? "" : path.substring(0, slash);
    }

    private static String join(String directory, String href) {
        return directory.isBlank() ? href : directory + "/" + href;
    }

    private static String sha256(String text) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private record Archive(Map<String, byte[]> entries) {
        static Archive read(byte[] content, EpubParserProperties properties) {
            try (ZipInputStream zip = new ZipInputStream(new ByteArrayInputStream(content), StandardCharsets.UTF_8)) {
                Map<String, byte[]> entries = new HashMap<>();
                byte[] buffer = new byte[BUFFER_SIZE];
                long expandedBytes = 0;
                ZipEntry entry;
                while ((entry = zip.getNextEntry()) != null) {
                    if (entry.isDirectory()) {
                        continue;
                    }
                    String name = normalizedName(entry.getName());
                    if (entries.size() >= properties.maxEntries()) {
                        throw new EpubParserException("EPUB archive exceeds the maximum entry count.");
                    }
                    byte[] entryContent = readEntry(zip, buffer, properties.maxEntrySize().toBytes());
                    expandedBytes += entryContent.length;
                    if (expandedBytes > properties.maxExpandedSize().toBytes()) {
                        throw new EpubParserException("EPUB archive exceeds the maximum expanded size.");
                    }
                    entries.put(name, entryContent);
                }
                if (entries.isEmpty()) {
                    throw new EpubParserException("Uploaded file is not a valid EPUB archive.");
                }
                return new Archive(entries);
            } catch (EpubParserException e) {
                throw e;
            } catch (Exception e) {
                throw new EpubParserException("Uploaded file is not a valid EPUB archive.", e);
            }
        }

        private static byte[] readEntry(ZipInputStream zip, byte[] buffer, long maxEntryBytes) throws java.io.IOException {
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            int read;
            long entryBytes = 0;
            while ((read = zip.read(buffer)) != -1) {
                entryBytes += read;
                if (entryBytes > maxEntryBytes) {
                    throw new EpubParserException("EPUB archive entry exceeds the maximum size.");
                }
                output.write(buffer, 0, read);
            }
            return output.toByteArray();
        }

        private static String normalizedName(String name) {
            if (name == null || name.isBlank()) {
                throw new EpubParserException("EPUB archive contains an invalid member name.");
            }
            String normalized = name.replace('\\', '/');
            if (normalized.startsWith("/") || normalized.contains("../") || normalized.startsWith("../") || normalized.contains("/..")) {
                throw new EpubParserException("EPUB archive contains an unsafe member path.");
            }
            return normalized;
        }

        byte[] get(String path) {
            byte[] content = entries.get(path);
            if (content == null) {
                throw new EpubParserException("EPUB archive is missing required member '" + path + "'.");
            }
            return content;
        }
    }
}
