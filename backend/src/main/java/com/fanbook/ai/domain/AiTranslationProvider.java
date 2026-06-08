package com.fanbook.ai.domain;

import java.util.List;

public interface AiTranslationProvider {
    String name();

    StructuredTranslationResult translateChunk(StructuredTranslationRequest request, String modelName);

    default StructuredGlossaryAnalysisResult analyzeGlossary(StructuredGlossaryAnalysisRequest request, String modelName) {
        return new StructuredGlossaryAnalysisResult(List.of(), name(), modelName == null ? "" : modelName);
    }

    default StructuredTranslationResult reviewTranslations(StructuredTranslationReviewRequest request, String modelName) {
        return translateChunk(toTranslationRequest(request), modelName);
    }

    default StructuredTranslationResult translateChunk(StructuredTranslationRequest request) {
        return translateChunk(request, "");
    }

    default StructuredTranslationResult reviewTranslations(StructuredTranslationReviewRequest request) {
        return reviewTranslations(request, "");
    }

    default StructuredGlossaryAnalysisResult analyzeGlossary(StructuredGlossaryAnalysisRequest request) {
        return analyzeGlossary(request, "");
    }

    private static StructuredTranslationRequest toTranslationRequest(StructuredTranslationReviewRequest request) {
        return new StructuredTranslationRequest(
                request.sourceLanguage(),
                request.targetLanguage(),
                request.bookTitle(),
                request.chapterTitle(),
                request.promptProfile(),
                request.preservation(),
                List.of(),
                request.glossary(),
                request.items().stream()
                        .map(item -> new StructuredTranslationSourceItem(
                                item.segmentId(),
                                """
                                        Review the existing target-language translation below. Fix only the listed issues and return the corrected translation text.

                                        Source:
                                        %s

                                        Current translation:
                                        %s

                                        Quality warnings:
                                        %s
                                        """.formatted(
                                        item.sourceText(),
                                        item.translatedText(),
                                        item.warnings().isEmpty() ? "low_quality_score" : String.join(", ", item.warnings())
                                )
                        ))
                        .toList()
        );
    }
}
