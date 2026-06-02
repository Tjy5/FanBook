package com.fanbook.book.api;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.OffsetDateTime;
import java.util.List;

public record BookListResponse(
        List<BookListItemDto> books,
        @JsonProperty("status_counts") StatusCountsDto statusCounts
) {
    public record BookListItemDto(
            Long id,
            String title,
            @JsonProperty("translated_title") String translatedTitle,
            @JsonProperty("title_translation_status") String titleTranslationStatus,
            String filename,
            @JsonProperty("source_language") String sourceLanguage,
            String status,
            double progress,
            @JsonProperty("total_segments") int totalSegments,
            @JsonProperty("translated_segments") int translatedSegments,
            @JsonProperty("failed_segments") int failedSegments,
            @JsonProperty("current_job_status") String currentJobStatus,
            @JsonProperty("created_at") OffsetDateTime createdAt,
            @JsonProperty("updated_at") OffsetDateTime updatedAt
    ) {
    }

    public record StatusCountsDto(int total, int running, int completed, int failed) {
    }
}
