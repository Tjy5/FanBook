package com.fanbook.book.application;

import com.fanbook.book.domain.SegmentType;

public record ParsedSegment(int order, String sourceText, SegmentType segmentType, String locatorJson, String sourceDigest) {
}
