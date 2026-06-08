package com.fanbook.translation.config;

import com.fanbook.ai.domain.StructuredTranslationGlossaryItem;
import java.util.List;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "fanbook.translation")
public record TranslationChunkPlanningProperties(
        int chunkTargetCharacters,
        int maxSegmentsPerChunk,
        int contextWindowSegments,
        int glossaryCandidateLimit,
        List<StructuredTranslationGlossaryItem> glossary
) {
    public TranslationChunkPlanningProperties {
        if (chunkTargetCharacters <= 0) {
            chunkTargetCharacters = 6000;
        }
        if (maxSegmentsPerChunk <= 0) {
            maxSegmentsPerChunk = 40;
        }
        if (contextWindowSegments < 0) {
            contextWindowSegments = 0;
        }
        if (glossaryCandidateLimit < 0) {
            glossaryCandidateLimit = 0;
        }
        glossary = glossary == null ? List.of() : List.copyOf(glossary);
    }
}
