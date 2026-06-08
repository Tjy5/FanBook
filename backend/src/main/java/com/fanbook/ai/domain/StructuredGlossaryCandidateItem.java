package com.fanbook.ai.domain;

public record StructuredGlossaryCandidateItem(
        String sourceTerm,
        String targetTerm,
        String category,
        String note,
        Long segmentId
) {
}
