package com.fanbook.common.error;

public record ApiErrorResponse(String code, String message, String traceId) {
}
