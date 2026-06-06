package com.fanbook.export.api;

public record ExportArtifactResponse(
        Long artifactId,
        Long bookId,
        String kind,
        String status,
        String filename,
        Long sizeBytes,
        String checksum
) {
}
