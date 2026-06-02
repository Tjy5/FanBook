package com.fanbook.translation.api;

public record TranslationJobResponse(
        Long jobId,
        Long bookId,
        String status,
        String providerName,
        String modelName,
        double progress,
        int totalSegments,
        int translatedSegments,
        int failedSegments
) {
}
