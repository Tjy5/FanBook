package com.fanbook.ai.api;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public record ProviderProfilesResponse(
        @JsonProperty("default_profile_name") String defaultProfileName,
        List<ProviderProfileDto> providers
) {
    public record ProviderProfileDto(
            @JsonProperty("profile_name") String profileName,
            @JsonProperty("provider_name") String providerName,
            @JsonProperty("default_model_name") String defaultModelName,
            boolean configured,
            @JsonProperty("max_requests_per_minute") Integer maxRequestsPerMinute,
            @JsonProperty("global_max_concurrency") int globalMaxConcurrency,
            @JsonProperty("per_chapter_concurrency") int perChapterConcurrency,
            @JsonProperty("is_default") boolean defaultProfile,
            String endpoint,
            @JsonProperty("uses_chat_completions") boolean usesChatCompletions,
            @JsonProperty("thinking_mode") String thinkingMode,
            @JsonProperty("json_mode") boolean jsonMode,
            @JsonProperty("min_request_interval_seconds") long minRequestIntervalSeconds,
            @JsonProperty("request_timeout_seconds") long requestTimeoutSeconds,
            @JsonProperty("messaging_prefetch") int messagingPrefetch,
            @JsonProperty("messaging_concurrency") int messagingConcurrency,
            @JsonProperty("messaging_listener_auto_startup") boolean messagingListenerAutoStartup,
            @JsonProperty("chunk_target_characters") int chunkTargetCharacters,
            @JsonProperty("max_segments_per_chunk") int maxSegmentsPerChunk,
            @JsonProperty("max_attempts_per_chunk") int maxAttemptsPerChunk,
            @JsonProperty("paid_safety_level") String paidSafetyLevel
    ) {
    }
}
