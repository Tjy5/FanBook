package com.fanbook.ai.domain;

import java.util.List;

public record StructuredTranslationResult(List<StructuredTranslationItem> items, String providerName, String modelName) {
}
