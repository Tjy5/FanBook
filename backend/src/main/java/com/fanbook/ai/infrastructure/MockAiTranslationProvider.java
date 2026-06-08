package com.fanbook.ai.infrastructure;

import com.fanbook.ai.domain.AiTranslationProvider;
import com.fanbook.ai.domain.StructuredGlossaryAnalysisRequest;
import com.fanbook.ai.domain.StructuredGlossaryAnalysisResult;
import com.fanbook.ai.domain.StructuredGlossaryCandidateItem;
import com.fanbook.ai.domain.StructuredTranslationItem;
import com.fanbook.ai.domain.StructuredTranslationReviewRequest;
import com.fanbook.ai.domain.StructuredTranslationRequest;
import com.fanbook.ai.domain.StructuredTranslationResult;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(name = "fanbook.ai.provider", havingValue = "mock", matchIfMissing = true)
public class MockAiTranslationProvider implements AiTranslationProvider {

    @Override
    public String name() {
        return "mock";
    }

    @Override
    public StructuredTranslationResult translateChunk(StructuredTranslationRequest request, String modelName) {
        List<StructuredTranslationItem> translated = request.items().stream()
                .map(item -> new StructuredTranslationItem(item.segmentId(), "[zh] " + item.sourceText()))
                .toList();
        String resolvedModelName = modelName == null || modelName.isBlank() ? "mock-translator" : modelName;
        return new StructuredTranslationResult(translated, name(), resolvedModelName);
    }

    @Override
    public StructuredTranslationResult reviewTranslations(StructuredTranslationReviewRequest request, String modelName) {
        List<StructuredTranslationItem> reviewed = request.items().stream()
                .map(item -> new StructuredTranslationItem(item.segmentId(), revised(item.sourceText(), item.translatedText())))
                .toList();
        String resolvedModelName = modelName == null || modelName.isBlank() ? "mock-translator" : modelName;
        return new StructuredTranslationResult(reviewed, name(), resolvedModelName);
    }

    @Override
    public StructuredGlossaryAnalysisResult analyzeGlossary(StructuredGlossaryAnalysisRequest request, String modelName) {
        Map<String, StructuredGlossaryCandidateItem> candidates = new LinkedHashMap<>();
        for (var item : request.items()) {
            for (String token : item.sourceText().split("[^\\p{L}\\p{N}']+")) {
                if (token.length() >= 4 && Character.isUpperCase(token.codePointAt(0))) {
                    candidates.putIfAbsent(token, new StructuredGlossaryCandidateItem(
                            token,
                            null,
                            "proper_noun",
                            "Mock extracted candidate; confirm before strict use.",
                            item.segmentId()
                    ));
                }
            }
        }
        String resolvedModelName = modelName == null || modelName.isBlank() ? "mock-translator" : modelName;
        return new StructuredGlossaryAnalysisResult(List.copyOf(candidates.values()), name(), resolvedModelName);
    }

    private static String revised(String sourceText, String translatedText) {
        String revised = translatedText == null ? "" : translatedText;
        if (sourceText != null && !sourceText.isBlank()) {
            revised = revised.replace(sourceText, "");
        }
        revised = revised.trim().replaceAll("\\s+", " ");
        if (revised.isBlank()) {
            revised = "已审校译文";
        }
        return "[reviewed] " + revised;
    }
}
