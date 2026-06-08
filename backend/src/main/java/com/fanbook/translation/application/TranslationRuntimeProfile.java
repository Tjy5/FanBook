package com.fanbook.translation.application;

import java.util.List;

public record TranslationRuntimeProfile(
        String providerName,
        String modelName,
        boolean configured,
        boolean realProvider,
        boolean safeToStart,
        String paidSafetyLevel,
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
        List<String> warnings,
        List<String> recommendations
) {
}
