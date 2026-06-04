package com.fanbook.reader.api;

import java.time.OffsetDateTime;

public record SegmentNoteResponse(
        Long noteId,
        Long bookId,
        Long segmentId,
        String content,
        String highlightColor,
        String createdBy,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
}
