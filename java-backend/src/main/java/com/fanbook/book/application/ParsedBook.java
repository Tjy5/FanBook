package com.fanbook.book.application;

import java.util.List;

public record ParsedBook(String title, List<ParsedChapter> chapters) {
}
