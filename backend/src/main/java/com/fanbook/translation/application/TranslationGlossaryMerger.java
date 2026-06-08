package com.fanbook.translation.application;

import com.fanbook.ai.domain.StructuredTranslationGlossaryItem;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public class TranslationGlossaryMerger {

    public enum MergeMode {
        OVERWRITE,
        FILL_EMPTY
    }

    public MergeResult merge(
            List<StructuredTranslationGlossaryItem> existing,
            List<StructuredTranslationGlossaryItem> incoming,
            MergeMode mode
    ) {
        Map<String, StructuredTranslationGlossaryItem> byTerm = new LinkedHashMap<>();
        int skippedEmpty = 0;
        int added = 0;
        int updated = 0;
        int filled = 0;
        List<MergeConflict> conflicts = new ArrayList<>();

        for (StructuredTranslationGlossaryItem item : existing == null ? List.<StructuredTranslationGlossaryItem>of() : existing) {
            String key = key(item.sourceTerm());
            if (key.isBlank()) {
                skippedEmpty++;
                continue;
            }
            byTerm.putIfAbsent(key, normalize(item));
        }

        for (StructuredTranslationGlossaryItem item : incoming == null ? List.<StructuredTranslationGlossaryItem>of() : incoming) {
            String key = key(item.sourceTerm());
            if (key.isBlank()) {
                skippedEmpty++;
                continue;
            }
            StructuredTranslationGlossaryItem normalized = normalize(item);
            StructuredTranslationGlossaryItem current = byTerm.get(key);
            if (current == null) {
                byTerm.put(key, normalized);
                added++;
                continue;
            }
            MergeOneResult merged = mergeOne(current, normalized, mode, key);
            conflicts.addAll(merged.conflicts());
            if (merged.updated()) {
                updated++;
            }
            if (merged.filled()) {
                filled++;
            }
            byTerm.put(key, merged.item());
        }

        return new MergeResult(List.copyOf(byTerm.values()), added, updated, filled, skippedEmpty, List.copyOf(conflicts));
    }

    private MergeOneResult mergeOne(
            StructuredTranslationGlossaryItem existing,
            StructuredTranslationGlossaryItem incoming,
            MergeMode mode,
            String key
    ) {
        List<MergeConflict> conflicts = new ArrayList<>();
        boolean updated = false;
        boolean filled = false;

        String sourceTerm = existing.sourceTerm();
        String targetTerm = existing.targetTerm();
        String category = existing.category();
        String note = existing.note();

        if (mode == MergeMode.OVERWRITE) {
            conflicts.addAll(conflicts(key, existing, incoming));
            updated = !same(existing, incoming);
            return new MergeOneResult(incoming, updated, false, List.copyOf(conflicts));
        }

        if (!blank(existing.targetTerm()) && !blank(incoming.targetTerm()) && !existing.targetTerm().equals(incoming.targetTerm())) {
            conflicts.add(new MergeConflict(key, "targetTerm", existing.targetTerm(), incoming.targetTerm()));
        } else if (blank(targetTerm) && !blank(incoming.targetTerm())) {
            targetTerm = incoming.targetTerm();
            filled = true;
        }
        if (blank(category) && !blank(incoming.category())) {
            category = incoming.category();
            filled = true;
        }
        if (blank(note) && !blank(incoming.note())) {
            note = incoming.note();
            filled = true;
        } else if (!blank(existing.note()) && !blank(incoming.note()) && !existing.note().equals(incoming.note())) {
            conflicts.add(new MergeConflict(key, "note", existing.note(), incoming.note()));
        }

        return new MergeOneResult(
                new StructuredTranslationGlossaryItem(sourceTerm, targetTerm, category, note),
                false,
                filled,
                List.copyOf(conflicts)
        );
    }

    private static List<MergeConflict> conflicts(
            String key,
            StructuredTranslationGlossaryItem existing,
            StructuredTranslationGlossaryItem incoming
    ) {
        List<MergeConflict> conflicts = new ArrayList<>();
        if (!blank(existing.targetTerm()) && !blank(incoming.targetTerm()) && !existing.targetTerm().equals(incoming.targetTerm())) {
            conflicts.add(new MergeConflict(key, "targetTerm", existing.targetTerm(), incoming.targetTerm()));
        }
        if (!blank(existing.note()) && !blank(incoming.note()) && !existing.note().equals(incoming.note())) {
            conflicts.add(new MergeConflict(key, "note", existing.note(), incoming.note()));
        }
        return conflicts;
    }

    private static StructuredTranslationGlossaryItem normalize(StructuredTranslationGlossaryItem item) {
        return new StructuredTranslationGlossaryItem(
                trim(item.sourceTerm()),
                trimToNull(item.targetTerm()),
                trimToNull(item.category()),
                trimToNull(item.note())
        );
    }

    private static boolean same(StructuredTranslationGlossaryItem first, StructuredTranslationGlossaryItem second) {
        return java.util.Objects.equals(first.sourceTerm(), second.sourceTerm())
                && java.util.Objects.equals(first.targetTerm(), second.targetTerm())
                && java.util.Objects.equals(first.category(), second.category())
                && java.util.Objects.equals(first.note(), second.note());
    }

    public static String key(String sourceTerm) {
        return trim(sourceTerm).toLowerCase(Locale.ROOT);
    }

    private static String trim(String value) {
        return value == null ? "" : value.trim();
    }

    private static String trimToNull(String value) {
        String trimmed = trim(value);
        return trimmed.isBlank() ? null : trimmed;
    }

    private static boolean blank(String value) {
        return value == null || value.isBlank();
    }

    private record MergeOneResult(
            StructuredTranslationGlossaryItem item,
            boolean updated,
            boolean filled,
            List<MergeConflict> conflicts
    ) {
    }

    public record MergeConflict(String sourceTermKey, String field, String existingValue, String incomingValue) {
    }

    public record MergeResult(
            List<StructuredTranslationGlossaryItem> items,
            int added,
            int updated,
            int filled,
            int skippedEmpty,
            List<MergeConflict> conflicts
    ) {
    }
}
