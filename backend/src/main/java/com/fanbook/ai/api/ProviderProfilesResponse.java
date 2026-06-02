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
            @JsonProperty("is_default") boolean defaultProfile
    ) {
    }
}
