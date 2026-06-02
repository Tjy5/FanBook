package com.fanbook.common.error;

import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.support.MissingServletRequestPartException;

@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(FanbookException.class)
    ResponseEntity<ApiErrorResponse> fanbook(FanbookException exception) {
        return ResponseEntity.status(exception.status()).body(response(exception.code(), exception.getMessage()));
    }

    @ExceptionHandler({MissingServletRequestPartException.class, MissingServletRequestParameterException.class})
    ResponseEntity<ApiErrorResponse> badRequest(Exception exception) {
        return ResponseEntity.badRequest().body(response(ErrorCode.INVALID_REQUEST, exception.getMessage()));
    }

    @ExceptionHandler(Exception.class)
    ResponseEntity<ApiErrorResponse> internal(Exception exception) {
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(response(ErrorCode.PROVIDER_REQUEST_FAILED, exception.getMessage()));
    }

    private static ApiErrorResponse response(ErrorCode code, String message) {
        return new ApiErrorResponse(code.value(), message, UUID.randomUUID().toString().replace("-", ""));
    }
}
