package com.fanbook.translation.api;

import java.util.List;

public record GlossaryAnalysisResponse(
        Long bookId,
        String providerName,
        String modelName,
        int analyzedSegments,
        int candidateCount,
        int persistedCandidates,
        List<GlossaryCandidateResponse> candidates
) {
}
