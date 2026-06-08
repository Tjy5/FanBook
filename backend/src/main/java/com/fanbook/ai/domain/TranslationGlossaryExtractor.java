package com.fanbook.ai.domain;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

public final class TranslationGlossaryExtractor {

    private static final Pattern CANDIDATE = Pattern.compile(
            "\\b(?:[A-Z][a-z]{2,}|[A-Z]{2,})(?:\\s+(?:of|the|and|for|in|on|[A-Z][a-z]{2,}|[A-Z]{2,}))*\\b"
    );
    private static final Set<String> STOP_TERMS = Set.of(
            "A", "An", "And", "As", "At", "Book", "Chapter", "For", "From", "He", "Her", "His",
            "I", "In", "It", "One", "She", "That", "The", "This", "To", "We", "You"
    );

    private TranslationGlossaryExtractor() {
    }

    public static List<StructuredTranslationGlossaryItem> extract(List<String> texts, int limit) {
        if (texts == null || texts.isEmpty() || limit <= 0) {
            return List.of();
        }
        Map<String, String> termsByKey = new LinkedHashMap<>();
        for (String text : texts) {
            if (text == null || text.isBlank()) {
                continue;
            }
            var matcher = CANDIDATE.matcher(text);
            while (matcher.find() && termsByKey.size() < limit) {
                String term = normalizeTerm(matcher.group());
                if (isUsefulTerm(term)) {
                    termsByKey.putIfAbsent(term.toLowerCase(Locale.ROOT), term);
                }
            }
            if (termsByKey.size() >= limit) {
                break;
            }
        }
        return termsByKey.values().stream()
                .map(term -> new StructuredTranslationGlossaryItem(
                        term,
                        null,
                        term.contains(" ") ? "proper_noun_phrase" : "proper_noun",
                        "Auto-extracted candidate; keep one consistent translation throughout the book."
                ))
                .toList();
    }

    private static String normalizeTerm(String term) {
        return term == null ? "" : term.trim().replaceAll("\\s+", " ");
    }

    private static boolean isUsefulTerm(String term) {
        if (term.length() < 4 || term.length() > 80 || STOP_TERMS.contains(term)) {
            return false;
        }
        String firstWord = term.split(" ")[0];
        return !STOP_TERMS.contains(firstWord);
    }
}
