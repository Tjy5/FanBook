package com.fanbook.reader.api;

import com.fanbook.translation.api.TranslationJobResponse;

public record ReaderInfoResponse(
        Long bookId,
        String title,
        String sourceLanguage,
        TranslationJobResponse latestJob
) {
}
