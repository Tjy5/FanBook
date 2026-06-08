package com.fanbook.translation.api;

import java.util.List;

public record TranslationReviewResponse(
        Long bookId,
        String providerName,
        String modelName,
        boolean applied,
        int minScore,
        int maxSegments,
        List<String> warningCodes,
        int candidateSegments,
        int selectedSegments,
        int reviewedSegments,
        int updatedSegments,
        List<TranslationReviewSegmentResponse> segments
) {
}
