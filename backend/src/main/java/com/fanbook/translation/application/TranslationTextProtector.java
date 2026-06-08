package com.fanbook.translation.application;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;
import org.springframework.stereotype.Component;

@Component
public class TranslationTextProtector {

    private static final Pattern URL = Pattern.compile("https?://\\S+|www\\.\\S+");
    private static final Pattern EMAIL = Pattern.compile("[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}");
    private static final Pattern FOOTNOTE = Pattern.compile("\\[[0-9A-Za-z]+]|\\([0-9A-Za-z]+\\)");
    private static final Pattern INLINE_TAG = Pattern.compile("</?[A-Za-z][^>]{0,120}>");
    private static final Pattern LIST_PREFIX = Pattern.compile("^\\s*(?:[0-9]+[.)]|[A-Za-z][.)]|[-*+])\\s+");
    private static final Pattern CODE_LIKE = Pattern.compile(
            "(?s)```.+?```|`[^`]+`|\\$[^$]+\\$|\\\\[A-Za-z]+\\{[^}]{1,120}}"
    );
    private static final Pattern MEASUREMENT = Pattern.compile(
            "\\b\\d+(?:\\.\\d+)?\\s?(?:kg|g|mg|km|cm|mm|m|mi|ft|in|mph|km/h|ml|mL|L|KB|MB|GB|Hz|kHz|MHz|GHz|V|W|kW|%)\\b|\\b\\d+(?:\\.\\d+)?\\s?[°℃℉](?:C|F)?\\b"
    );
    private static final Pattern TECHNICAL_IDENTIFIER = Pattern.compile(
            "\\b[A-Z]{2,}[A-Z0-9_-]*\\d+[A-Z0-9_-]*\\b|\\b[A-Za-z]+(?:[._-][A-Za-z0-9]+){2,}\\b"
    );

    public List<String> missingPreservedTokens(String source, String translated, TranslationPreservationOptions options) {
        if (source == null || translated == null) {
            return List.of();
        }
        List<String> tokens = new ArrayList<>();
        TranslationPreservationOptions safe = options == null ? TranslationPreservationOptions.defaults() : options;
        if (safe.urls()) {
            addMatches(tokens, URL, source);
        }
        if (safe.emails()) {
            addMatches(tokens, EMAIL, source);
        }
        if (safe.footnoteMarkers()) {
            addMatches(tokens, FOOTNOTE, source);
        }
        if (safe.inlineMarkup()) {
            addMatches(tokens, INLINE_TAG, source);
        }
        if (safe.listNumbering()) {
            addMatches(tokens, LIST_PREFIX, source);
        }
        if (safe.codeLikeSpans()) {
            addMatches(tokens, CODE_LIKE, source);
            addMatches(tokens, MEASUREMENT, source);
            addMatches(tokens, TECHNICAL_IDENTIFIER, source);
        }
        return tokens.stream()
                .filter(token -> !translated.contains(token))
                .distinct()
                .toList();
    }

    public String postProcess(String translated) {
        if (translated == null) {
            return "";
        }
        return translated
                .replace("\u00a0", " ")
                .replaceAll("[ \\t]+\\n", "\n")
                .replaceAll("\\n{3,}", "\n\n")
                .trim();
    }

    private static void addMatches(List<String> tokens, Pattern pattern, String source) {
        var matcher = pattern.matcher(source);
        while (matcher.find()) {
            String value = matcher.group();
            if (value != null && !value.isBlank()) {
                tokens.add(value.trim());
            }
        }
    }
}
