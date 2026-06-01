package com.fanbook.book.api;

public record BookResponse(Long bookId, String title, String status, int chapters, int segments) {
}
