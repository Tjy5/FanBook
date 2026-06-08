package com.fanbook.ai.infrastructure;

import com.fanbook.ai.domain.AiTranslationProvider;
import com.fanbook.ai.domain.StructuredTranslationItem;
import com.fanbook.ai.domain.StructuredTranslationReviewRequest;
import com.fanbook.ai.domain.StructuredTranslationRequest;
import com.fanbook.ai.domain.StructuredTranslationResult;
import java.util.List;
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
