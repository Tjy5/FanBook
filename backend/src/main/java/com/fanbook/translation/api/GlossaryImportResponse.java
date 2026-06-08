package com.fanbook.translation.api;

import java.util.List;

public record GlossaryImportResponse(
        Long bookId,
        int acceptedCandidates,
        int conflicts,
        List<GlossaryCandidateResponse> candidates
) {
}
