package com.fanbook.book.api;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.OffsetDateTime;
import java.util.List;

public record BookDetailResponse(
        BookDto book,
        @JsonProperty("current_job") JobDto currentJob,
        List<ChapterDto> chapters,
        List<ArtifactDto> artifacts
) {
    public record BookDto(
            Long id,
            String title,
            @JsonProperty("translated_title") String translatedTitle,
            @JsonProperty("title_translation_status") String titleTranslationStatus,
            String filename,
            @JsonProperty("source_language") String sourceLanguage,
            String status,
            @JsonProperty("created_at") OffsetDateTime createdAt,
            @JsonProperty("updated_at") OffsetDateTime updatedAt
    ) {
    }

    public record JobDto(
            @JsonProperty("job_id") Long jobId,
            @JsonProperty("book_id") Long bookId,
            String status,
            @JsonProperty("provider_profile_name") String providerProfileName,
            @JsonProperty("provider_name") String providerName,
            @JsonProperty("model_name") String modelName,
            double progress,
            @JsonProperty("total_segments") int totalSegments,
            @JsonProperty("translated_segments") int translatedSegments,
            @JsonProperty("failed_segments") int failedSegments,
            @JsonProperty("estimated_remaining_seconds") Long estimatedRemainingSeconds,
            @JsonProperty("created_at") OffsetDateTime createdAt,
            @JsonProperty("updated_at") OffsetDateTime updatedAt
    ) {
    }

    public record ChapterDto(
            Long id,
            int order,
            String title,
            @JsonProperty("total_segments") int totalSegments,
            @JsonProperty("translated_segments") int translatedSegments,
            @JsonProperty("failed_segments") int failedSegments
    ) {
    }

    public record ArtifactDto(
            Long id,
            String kind,
            String status,
            String filename,
            Long size,
            @JsonProperty("created_at") OffsetDateTime createdAt
    ) {
    }
}
