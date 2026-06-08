package com.fanbook.book.application;

import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Document;

public final class EpubXmlDocuments {

    private static final Pattern DOCTYPE = Pattern.compile("(?is)<!DOCTYPE[^>]*>");
    private static final Pattern HTML_TAG = Pattern.compile("(?is)<html(?<attributes>[^>]*)>");
    private static final Pattern VOID_TAG = Pattern.compile(
            "(?i)<(?<name>area|base|br|col|embed|hr|img|input|link|meta|param|source|track|wbr)(?<attributes>\\s[^<>]*)?>"
    );

    private EpubXmlDocuments() {
    }

    public static Document parse(byte[] content, String path) {
        try {
            return parseXml(content);
        } catch (Exception xmlException) {
            if (!isHtmlDocument(path)) {
                throw new EpubParserException("EPUB document '" + path + "' is not well-formed XML.", xmlException);
            }
            try {
                return parseXml(htmlToXhtml(content));
            } catch (Exception htmlException) {
                throw new EpubParserException("EPUB document '" + path + "' is not well-formed XML.", htmlException);
            }
        }
    }

    private static Document parseXml(byte[] content) throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setNamespaceAware(true);
        factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        return factory.newDocumentBuilder().parse(new ByteArrayInputStream(content));
    }

    private static byte[] htmlToXhtml(byte[] content) {
        String html = new String(content, StandardCharsets.UTF_8)
                .replaceFirst("^\\uFEFF", "")
                .replace("&nbsp;", "&#160;");
        html = DOCTYPE.matcher(html).replaceAll("");
        html = addXhtmlNamespace(html);
        html = selfCloseVoidTags(html);
        return html.getBytes(StandardCharsets.UTF_8);
    }

    private static String addXhtmlNamespace(String html) {
        Matcher matcher = HTML_TAG.matcher(html);
        if (!matcher.find() || matcher.group("attributes").toLowerCase().contains("xmlns")) {
            return html;
        }
        return matcher.replaceFirst(Matcher.quoteReplacement(
                "<html xmlns=\"http://www.w3.org/1999/xhtml\"" + matcher.group("attributes") + ">"
        ));
    }

    private static String selfCloseVoidTags(String html) {
        Matcher matcher = VOID_TAG.matcher(html);
        StringBuffer result = new StringBuffer();
        while (matcher.find()) {
            String attributes = matcher.group("attributes") == null ? "" : matcher.group("attributes");
            String replacement = attributes.trim().endsWith("/")
                    ? matcher.group()
                    : "<" + matcher.group("name") + attributes + "/>";
            matcher.appendReplacement(result, Matcher.quoteReplacement(replacement));
        }
        matcher.appendTail(result);
        return result.toString();
    }

    private static boolean isHtmlDocument(String path) {
        String normalized = path == null ? "" : path.toLowerCase();
        return normalized.endsWith(".html") || normalized.endsWith(".htm") || normalized.endsWith(".xhtml");
    }
}
