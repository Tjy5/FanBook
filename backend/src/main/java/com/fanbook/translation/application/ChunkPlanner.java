package com.fanbook.translation.application;

import com.fanbook.book.domain.SegmentEntity;
import com.fanbook.book.domain.SegmentType;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

public class ChunkPlanner {

    private final int targetCharacters;
    private final int maxSegmentsPerChunk;

    public ChunkPlanner(int targetCharacters, int maxSegmentsPerChunk) {
        this.targetCharacters = targetCharacters;
        this.maxSegmentsPerChunk = maxSegmentsPerChunk;
    }

    public List<List<SegmentEntity>> plan(List<SegmentEntity> segments) {
        List<List<SegmentEntity>> chunks = new ArrayList<>();
        List<SegmentEntity> current = new ArrayList<>();
        int currentCharacters = 0;
        for (SemanticUnit unit : semanticUnits(segments)) {
            boolean fullByCount = !current.isEmpty() && current.size() + unit.segments().size() > maxSegmentsPerChunk;
            boolean fullBySize = !current.isEmpty() && currentCharacters + unit.characters() > targetCharacters;
            boolean crossesChapter = !current.isEmpty() && !sameChapter(current.getLast(), unit.segments().getFirst());
            boolean startsSection = !current.isEmpty() && unit.startsWithTitle();
            if (fullByCount || fullBySize || crossesChapter || startsSection) {
                chunks.add(List.copyOf(current));
                current.clear();
                currentCharacters = 0;
            }
            current.addAll(unit.segments());
            currentCharacters += unit.characters();
        }
        if (!current.isEmpty()) {
            chunks.add(List.copyOf(current));
        }
        return chunks;
    }

    private List<SemanticUnit> semanticUnits(List<SegmentEntity> segments) {
        List<SemanticUnit> units = new ArrayList<>();
        int index = 0;
        while (index < segments.size()) {
            SemanticUnit unit = semanticUnit(segments, index);
            units.add(unit);
            index += unit.segments().size();
        }
        return units;
    }

    private SemanticUnit semanticUnit(List<SegmentEntity> segments, int index) {
        SegmentEntity first = segments.get(index);
        if (first.getSegmentType() == SegmentType.TITLE) {
            return titleUnit(segments, index);
        }
        if (first.getSegmentType() == SegmentType.LIST_ITEM
                || first.getSegmentType() == SegmentType.QUOTE
                || first.getSegmentType() == SegmentType.POETRY
                || isDialogue(first)) {
            return runUnit(segments, index, first.getSegmentType());
        }
        return new SemanticUnit(List.of(first));
    }

    private SemanticUnit titleUnit(List<SegmentEntity> segments, int index) {
        SegmentEntity title = segments.get(index);
        List<SegmentEntity> unit = new ArrayList<>();
        unit.add(title);
        if (maxSegmentsPerChunk <= 1 || index + 1 >= segments.size()) {
            return new SemanticUnit(unit);
        }

        SegmentEntity next = segments.get(index + 1);
        if (next.getSegmentType() == SegmentType.TITLE || !sameChapter(title, next)) {
            return new SemanticUnit(unit);
        }

        SemanticUnit nextUnit = semanticUnit(segments, index + 1);
        if (unit.size() + nextUnit.segments().size() <= maxSegmentsPerChunk
                && title.getSourceText().length() + nextUnit.characters() <= targetCharacters) {
            unit.addAll(nextUnit.segments());
        }
        return new SemanticUnit(unit);
    }

    private SemanticUnit runUnit(List<SegmentEntity> segments, int index, SegmentType type) {
        List<SegmentEntity> unit = new ArrayList<>();
        int characters = 0;
        SegmentEntity first = segments.get(index);
        for (int i = index; i < segments.size(); i++) {
            SegmentEntity candidate = segments.get(i);
            if (!sameChapter(first, candidate) || candidate.getSegmentType() == SegmentType.TITLE) {
                break;
            }
            if (!sameRun(first, candidate, type)) {
                break;
            }
            int nextCharacters = candidate.getSourceText().length();
            boolean fullByCount = unit.size() >= maxSegmentsPerChunk;
            boolean fullBySize = !unit.isEmpty() && characters + nextCharacters > targetCharacters;
            if (fullByCount || fullBySize) {
                break;
            }
            unit.add(candidate);
            characters += nextCharacters;
        }
        if (unit.isEmpty()) {
            unit.add(first);
        }
        return new SemanticUnit(unit);
    }

    private static boolean sameRun(SegmentEntity first, SegmentEntity candidate, SegmentType type) {
        if (type == SegmentType.LIST_ITEM || type == SegmentType.QUOTE || type == SegmentType.POETRY) {
            return candidate.getSegmentType() == type;
        }
        return isDialogue(first) && isDialogue(candidate);
    }

    private static boolean isDialogue(SegmentEntity segment) {
        if (segment.getSegmentType() != SegmentType.PARAGRAPH) {
            return false;
        }
        String text = segment.getSourceText().strip();
        if (text.isEmpty()) {
            return false;
        }
        String lower = text.toLowerCase(Locale.ROOT);
        return text.startsWith("\"")
                || text.startsWith("'")
                || text.startsWith("“")
                || text.startsWith("‘")
                || text.startsWith("—")
                || text.startsWith("- ")
                || text.endsWith("\"")
                || text.endsWith("”")
                || lower.startsWith("he said")
                || lower.startsWith("she said")
                || lower.startsWith("said ");
    }

    private static boolean sameChapter(SegmentEntity left, SegmentEntity right) {
        Long leftId = left.getChapter().getId();
        Long rightId = right.getChapter().getId();
        if (leftId != null && rightId != null) {
            return leftId.equals(rightId);
        }
        return left.getChapter() == right.getChapter();
    }

    private record SemanticUnit(List<SegmentEntity> segments, int characters, boolean startsWithTitle) {
        SemanticUnit(List<SegmentEntity> segments) {
            this(
                    List.copyOf(segments),
                    segments.stream().mapToInt(segment -> segment.getSourceText().length()).sum(),
                    !segments.isEmpty() && segments.getFirst().getSegmentType() == SegmentType.TITLE
            );
        }
    }
}
