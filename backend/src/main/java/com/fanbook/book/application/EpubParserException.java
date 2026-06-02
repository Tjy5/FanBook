package com.fanbook.book.application;

public class EpubParserException extends RuntimeException {
    public EpubParserException(String message) {
        super(message);
    }

    public EpubParserException(String message, Throwable cause) {
        super(message, cause);
    }
}
