package com.fanbook.common.error;

public enum ErrorCode {
    INVALID_REQUEST("invalid_request"),
    UNAUTHENTICATED("unauthenticated"),
    FORBIDDEN("forbidden"),
    AUTHENTICATION_FAILED("authentication_failed"),
    USER_NOT_FOUND("user_not_found"),
    USER_ALREADY_EXISTS("user_already_exists"),
    LAST_ADMIN_REQUIRED("last_admin_required"),
    INVALID_EPUB("invalid_epub"),
    BOOK_NOT_FOUND("book_not_found"),
    BOOK_TRANSLATION_IN_PROGRESS("book_translation_in_progress"),
    TRANSLATION_ALREADY_RUNNING("translation_already_running"),
    TRANSLATION_ALREADY_COMPLETED("translation_already_completed"),
    TRANSLATION_JOB_NOT_FOUND("translation_job_not_found"),
    JOB_STILL_RUNNING("job_still_running"),
    PROVIDER_NOT_FOUND("provider_not_found"),
    PROVIDER_NOT_CONFIGURED("provider_not_configured"),
    PROVIDER_REQUEST_FAILED("provider_request_failed"),
    PROVIDER_RATE_LIMITED("provider_rate_limited"),
    PROVIDER_TIMEOUT("provider_timeout"),
    STRUCTURED_OUTPUT_INVALID("structured_output_invalid"),
    CHUNK_RETRY_EXHAUSTED("chunk_retry_exhausted"),
    EXPORT_NOT_READY("export_not_ready"),
    EXPORT_FAILED("export_failed");

    private final String value;

    ErrorCode(String value) {
        this.value = value;
    }

    public String value() {
        return value;
    }
}
