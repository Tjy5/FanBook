package com.fanbook.translation.api;

import java.util.List;

public record TranslationPreflightResponse(
        Long bookId,
        String providerName,
        String modelName,
        boolean configured,
        boolean realProvider,
        boolean safeToStart,
        String paidSafetyLevel,
        int totalSegments,
        int estimatedChunks,
        String endpoint,
        boolean usesChatCompletions,
        String thinkingMode,
        boolean jsonMode,
        int maxConcurrency,
        long minRequestIntervalSeconds,
        long requestTimeoutSeconds,
        int messagingPrefetch,
        int messagingConcurrency,
        boolean messagingListenerAutoStartup,
        int chunkTargetCharacters,
        int maxSegmentsPerChunk,
        int maxAttemptsPerChunk,
        long estimatedMinimumRuntimeSeconds,
        List<String> warnings,
        List<String> recommendations
) {
}
