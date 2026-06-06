package com.fanbook.translation.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "fanbook.translation")
public record TranslationChunkPlanningProperties(
        int chunkTargetCharacters,
        int maxSegmentsPerChunk
) {
    public TranslationChunkPlanningProperties {
        if (chunkTargetCharacters <= 0) {
            chunkTargetCharacters = 6000;
        }
        if (maxSegmentsPerChunk <= 0) {
            maxSegmentsPerChunk = 40;
        }
    }
}
