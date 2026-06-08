package com.fanbook.translation.api;

public record GlossaryCandidateResponse(
        Long candidateId,
        String sourceTerm,
        String targetTerm,
        String category,
        String note,
        String status,
        int evidenceCount,
        Long firstSegmentId
) {
}
