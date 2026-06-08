package com.fanbook.translation.application;

import com.fanbook.ai.domain.StructuredTranslationGlossaryItem;
import com.fanbook.book.application.SegmentInlineMarkup;
import com.fanbook.book.domain.SegmentEntity;
import com.fanbook.book.domain.SegmentStatus;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

public final class TranslationQualityAnalyzer {

    public TranslationQualityAnalysis analyze(
            List<SegmentEntity> segments,
            List<StructuredTranslationGlossaryItem> glossary
    ) {
        return analyze(segments, glossary, TranslationPreservationOptions.defaults());
    }

    public TranslationQualityAnalysis analyze(
            List<SegmentEntity> segments,
            List<StructuredTranslationGlossaryItem> glossary,
            TranslationPreservationOptions preservation
    ) {
        TranslationTextProtector textProtector = new TranslationTextProtector();
        List<ConsistencyWarning> warnings = new ArrayList<>();
        List<ConsistencyWarning> termWarnings = new ArrayList<>();
        List<SegmentQualityScore> segmentScores = new ArrayList<>();
        for (SegmentEntity segment : segments == null ? List.<SegmentEntity>of() : segments) {
            String source = normalized(segment.getSourceText());
            String translated = normalized(SegmentInlineMarkup.displayTranslatedText(segment));
            List<String> reasons = new ArrayList<>();
            int score = 100;
            if (segment.getStatus() == SegmentStatus.FAILED) {
                warnings.add(warning(
                        "segment_failed",
                        "error",
                        segment,
                        "Segment failed translation: " + valueOrFallback(segment.getLastErrorMessage(), "no error message")
                ));
                reasons.add("segment_failed");
                segmentScores.add(new SegmentQualityScore(segment.getId(), segment.getSegmentOrder(), 0, List.copyOf(reasons)));
                continue;
            }
            if (segment.getStatus() != SegmentStatus.TRANSLATED || translated.isBlank()) {
                warnings.add(warning(
                        "missing_translation",
                        "error",
                        segment,
                        "Segment has no translated text."
                ));
                reasons.add("missing_translation");
                segmentScores.add(new SegmentQualityScore(segment.getId(), segment.getSegmentOrder(), 0, List.copyOf(reasons)));
                continue;
            }
            if (source.length() >= 20 && translated.contains(source)) {
                warnings.add(warning(
                        "source_repeated_in_translation",
                        "warning",
                        segment,
                        "Translated text still contains the full source text."
                ));
                score -= 35;
                reasons.add("source_repeated_in_translation");
            }
            if (hasEnglishResidue(translated)) {
                warnings.add(warning(
                        "english_residue",
                        "warning",
                        segment,
                        "Translated text contains substantial English residue."
                ));
                score -= 20;
                reasons.add("english_residue");
            }
            if (hasSuspiciousLengthRatio(source, translated)) {
                warnings.add(warning(
                        "suspicious_length_ratio",
                        "warning",
                        segment,
                        "Translated length is suspicious compared with source length."
                ));
                score -= 20;
                reasons.add("suspicious_length_ratio");
            }
            List<String> missingTokens = textProtector.missingPreservedTokens(segment.getSourceText(), segment.getTranslatedText(), preservation);
            if (!missingTokens.isEmpty()) {
                warnings.add(warning(
                        "preserved_token_missing",
                        "warning",
                        segment,
                        "Translated text is missing preserved source token(s): " + String.join(", ", missingTokens)
                ));
                score -= 20;
                reasons.add("preserved_token_missing");
            }
            SegmentInlineMarkup.PlaceholderValidation placeholderValidation = SegmentInlineMarkup.validateTranslatedText(
                    segment.getTranslatedText(),
                    segment.getLocatorJson()
            );
            if (!placeholderValidation.valid()) {
                warnings.add(warning(
                        "placeholder_mismatch",
                        "warning",
                        segment,
                        "Inline placeholder mismatch: " + placeholderValidation.message()
                ));
                score -= 30;
                reasons.add("placeholder_mismatch");
            }
            for (var glossaryItem : glossary == null ? List.<StructuredTranslationGlossaryItem>of() : glossary) {
                if (hasGlossaryMismatch(source, translated, glossaryItem)) {
                    ConsistencyWarning warning = warning(
                            "glossary_term_missing",
                            "warning",
                            segment,
                            "Configured glossary term was not used: " + glossaryItem.sourceTerm() + " -> " + glossaryItem.targetTerm()
                    );
                    warnings.add(warning);
                    termWarnings.add(warning);
                    score -= 25;
                    reasons.add("glossary_term_missing");
                }
            }
            segmentScores.add(new SegmentQualityScore(segment.getId(), segment.getSegmentOrder(), Math.max(0, score), List.copyOf(reasons)));
        }
        int qualityScore = segmentScores.isEmpty()
                ? 0
                : (int) Math.round(segmentScores.stream().mapToInt(SegmentQualityScore::score).average().orElse(0));
        return new TranslationQualityAnalysis(
                qualityScore,
                List.copyOf(segmentScores),
                List.copyOf(warnings),
                List.copyOf(termWarnings)
        );
    }

    private static ConsistencyWarning warning(String code, String severity, SegmentEntity segment, String message) {
        return new ConsistencyWarning(
                code,
                severity,
                segment.getId(),
                segment.getSegmentOrder(),
                message,
                preview(segment.getSourceText()),
                preview(SegmentInlineMarkup.displayTranslatedText(segment))
        );
    }

    private static boolean hasEnglishResidue(String text) {
        if (text.isBlank()) {
            return false;
        }
        int tokenCount = 0;
        int letterCount = 0;
        var matcher = java.util.regex.Pattern.compile("[A-Za-z]{4,}").matcher(text);
        while (matcher.find()) {
            tokenCount++;
            letterCount += matcher.group().length();
        }
        return tokenCount >= 3 || letterCount >= 24;
    }

    private static boolean hasSuspiciousLengthRatio(String source, String translated) {
        if (source.length() < 30 || translated.isBlank()) {
            return false;
        }
        double ratio = (double) translated.length() / source.length();
        return ratio < 0.15 || ratio > 3.5;
    }

    private static boolean hasGlossaryMismatch(
            String source,
            String translated,
            StructuredTranslationGlossaryItem glossaryItem
    ) {
        if (glossaryItem.sourceTerm() == null
                || glossaryItem.sourceTerm().isBlank()
                || glossaryItem.targetTerm() == null
                || glossaryItem.targetTerm().isBlank()) {
            return false;
        }
        return source.toLowerCase(Locale.ROOT).contains(glossaryItem.sourceTerm().toLowerCase(Locale.ROOT))
                && !translated.contains(glossaryItem.targetTerm());
    }

    private static String normalized(String text) {
        return text == null ? "" : text.trim().replaceAll("\\s+", " ");
    }

    private static String preview(String text) {
        String normalized = normalized(text);
        return normalized.length() <= 160 ? normalized : normalized.substring(0, 157) + "...";
    }

    private static String valueOrFallback(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }

    public record TranslationQualityAnalysis(
            int qualityScore,
            List<SegmentQualityScore> segmentScores,
            List<ConsistencyWarning> warnings,
            List<ConsistencyWarning> termWarnings
    ) {
    }

    public record ConsistencyWarning(
            String code,
            String severity,
            Long segmentId,
            int segmentOrder,
            String message,
            String sourceText,
            String translatedText
    ) {
    }

    public record SegmentQualityScore(Long segmentId, int segmentOrder, int score, List<String> reasons) {
    }
}
