package com.fanbook.book.application;

import java.util.List;

public record ParsedChapter(int order, String title, String sourceDocPath, List<ParsedSegment> segments) {
}
