package com.fanbook.translation.application;

import com.fanbook.book.domain.SegmentEntity;
import java.util.ArrayList;
import java.util.List;

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
        for (SegmentEntity segment : segments) {
            int nextCharacters = segment.getSourceText().length();
            boolean fullByCount = current.size() >= maxSegmentsPerChunk;
            boolean fullBySize = !current.isEmpty() && currentCharacters + nextCharacters > targetCharacters;
            if (fullByCount || fullBySize) {
                chunks.add(List.copyOf(current));
                current.clear();
                currentCharacters = 0;
            }
            current.add(segment);
            currentCharacters += nextCharacters;
        }
        if (!current.isEmpty()) {
            chunks.add(List.copyOf(current));
        }
        return chunks;
    }
}
