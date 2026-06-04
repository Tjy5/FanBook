package com.fanbook.reader.api;

import java.util.List;

public record ChapterSegmentResponse(
        Long chapterId,
        String chapterTitle,
        List<ReaderSegment> segments
) {

    public record ReaderSegment(
            Long segmentId,
            int order,
            String type,
            String sourceText,
            String translatedText,
            String translationStatus,
            long noteCount
    ) {
    }
}
