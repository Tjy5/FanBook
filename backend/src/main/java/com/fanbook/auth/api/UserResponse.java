package com.fanbook.auth.api;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public record UserResponse(
        Long id,
        String username,
        String email,
        List<String> roles,
        @JsonProperty("csrf_token") String csrfToken,
        @JsonProperty("csrf_header_name") String csrfHeaderName
) {
}
