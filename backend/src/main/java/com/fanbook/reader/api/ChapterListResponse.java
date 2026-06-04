package com.fanbook.reader.api;

import java.util.List;

public record ChapterListResponse(List<ChapterSummary> chapters) {

    public record ChapterSummary(
            Long chapterId,
            int chapterOrder,
            String title,
            int totalSegments,
            int translatedSegments,
            double progress
    ) {
    }
}
