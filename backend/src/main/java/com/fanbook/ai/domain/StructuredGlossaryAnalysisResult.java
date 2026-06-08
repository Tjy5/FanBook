package com.fanbook.ai.domain;

import java.util.List;

public record StructuredGlossaryAnalysisResult(
        List<StructuredGlossaryCandidateItem> candidates,
        String providerName,
        String modelName
) {
    public StructuredGlossaryAnalysisResult {
        candidates = candidates == null ? List.of() : List.copyOf(candidates);
    }
}
