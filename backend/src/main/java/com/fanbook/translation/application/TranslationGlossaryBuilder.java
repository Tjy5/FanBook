package com.fanbook.translation.application;

import com.fanbook.ai.domain.StructuredTranslationGlossaryItem;
import com.fanbook.ai.domain.TranslationGlossaryExtractor;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

class TranslationGlossaryBuilder {

    List<StructuredTranslationGlossaryItem> build(
            List<StructuredTranslationGlossaryItem> configuredGlossary,
            List<String> requestTexts,
            int autoCandidateLimit
    ) {
        Map<String, StructuredTranslationGlossaryItem> byTerm = new LinkedHashMap<>();
        List<String> normalizedTexts = requestTexts == null ? List.of() : requestTexts.stream()
                .filter(text -> text != null && !text.isBlank())
                .toList();
        for (StructuredTranslationGlossaryItem item : configuredGlossary == null ? List.<StructuredTranslationGlossaryItem>of() : configuredGlossary) {
            if (item.sourceTerm() == null || item.sourceTerm().isBlank()) {
                continue;
            }
            if (isRelevant(item.sourceTerm(), normalizedTexts)) {
                byTerm.putIfAbsent(key(item.sourceTerm()), item);
            }
        }
        if (autoCandidateLimit > 0) {
            int autoAdded = 0;
            int extractionLimit = autoCandidateLimit + byTerm.size();
            for (StructuredTranslationGlossaryItem item : TranslationGlossaryExtractor.extract(normalizedTexts, extractionLimit)) {
                if (!byTerm.containsKey(key(item.sourceTerm()))) {
                    byTerm.put(key(item.sourceTerm()), item);
                    autoAdded++;
                }
                if (autoAdded >= autoCandidateLimit) {
                    break;
                }
            }
        }
        return List.copyOf(byTerm.values());
    }

    private static boolean isRelevant(String sourceTerm, List<String> texts) {
        String needle = sourceTerm.toLowerCase(Locale.ROOT);
        return texts.stream().anyMatch(text -> text.toLowerCase(Locale.ROOT).contains(needle));
    }

    private static String key(String sourceTerm) {
        return sourceTerm.trim().toLowerCase(Locale.ROOT);
    }
}
