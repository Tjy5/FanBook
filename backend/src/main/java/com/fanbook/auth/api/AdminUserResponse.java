package com.fanbook.auth.api;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.OffsetDateTime;
import java.util.List;

public record AdminUserResponse(
        Long id,
        String username,
        String email,
        boolean enabled,
        List<String> roles,
        @JsonProperty("created_at") OffsetDateTime createdAt,
        @JsonProperty("updated_at") OffsetDateTime updatedAt
) {
}
