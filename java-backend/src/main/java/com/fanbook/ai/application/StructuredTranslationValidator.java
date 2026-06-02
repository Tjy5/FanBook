package com.fanbook.ai.application;

import com.fanbook.ai.domain.StructuredTranslationResult;
import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

@Component
public class StructuredTranslationValidator {

    public void validate(List<Long> expectedSegmentIds, StructuredTranslationResult result) {
        Set<Long> expected = new HashSet<>(expectedSegmentIds);
        Set<Long> seen = new HashSet<>();
        for (var item : result.items()) {
            if (!expected.contains(item.segmentId())) {
                throw invalid("unexpected segment " + item.segmentId());
            }
            if (!seen.add(item.segmentId())) {
                throw invalid("duplicate segment " + item.segmentId());
            }
            if (item.translatedText() == null || item.translatedText().isBlank()) {
                throw invalid("empty translation for segment " + item.segmentId());
            }
        }
        for (Long segmentId : expected) {
            if (!seen.contains(segmentId)) {
                throw invalid("missing segment " + segmentId);
            }
        }
    }

    private FanbookException invalid(String message) {
        return new FanbookException(ErrorCode.STRUCTURED_OUTPUT_INVALID, HttpStatus.BAD_GATEWAY, message);
    }
}
