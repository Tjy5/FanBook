package com.fanbook.translation.api;

import java.util.List;

public record TranslationReviewSegmentResponse(
        Long segmentId,
        int segmentOrder,
        int score,
        List<String> warnings,
        boolean reviewed,
        boolean updated
) {
}
