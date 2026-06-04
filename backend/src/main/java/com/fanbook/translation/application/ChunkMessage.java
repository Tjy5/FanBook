package com.fanbook.translation.application;

import java.time.OffsetDateTime;

public record ChunkMessage(
        String schemaVersion,
        Long jobId,
        Long chunkId,
        int attemptNumber,
        String dispatchReason,
        String correlationId,
        OffsetDateTime requestedAt
) {
    public static ChunkMessage start(Long jobId, Long chunkId) {
        return new ChunkMessage(
                "1.0",
                jobId,
                chunkId,
                1,
                "START",
                "job-" + jobId + "-chunk-" + chunkId,
                OffsetDateTime.now()
        );
    }
}
