package com.fanbook.translation.application;

import com.fanbook.ai.domain.StructuredTranslationGlossaryItem;
import com.fanbook.ai.domain.TranslationPromptProfile;
import java.util.List;

public record TranslationRuleSnapshotData(
        Long snapshotId,
        String snapshotHash,
        String targetLanguage,
        TranslationPromptProfile promptProfile,
        TranslationPreservationOptions preservation,
        List<StructuredTranslationGlossaryItem> glossary
) {
    public TranslationRuleSnapshotData {
        promptProfile = promptProfile == null ? TranslationPromptProfile.defaults() : promptProfile;
        preservation = preservation == null ? TranslationPreservationOptions.defaults() : preservation;
        glossary = glossary == null ? List.of() : List.copyOf(glossary);
    }

    public String cachePromptVersion() {
        return snapshotHash == null || snapshotHash.isBlank() ? "v1" : snapshotHash.substring(0, Math.min(32, snapshotHash.length()));
    }
}
