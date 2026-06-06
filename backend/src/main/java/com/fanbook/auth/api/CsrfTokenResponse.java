package com.fanbook.auth.api;

import com.fasterxml.jackson.annotation.JsonProperty;

public record CsrfTokenResponse(
        String token,
        @JsonProperty("header_name") String headerName,
        @JsonProperty("parameter_name") String parameterName
) {
}
