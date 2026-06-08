package com.fanbook.translation.application;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fanbook.translation.domain.TranslationChunkEntity;
import com.fanbook.translation.domain.TranslationChunkStatus;
import com.fanbook.translation.infrastructure.TranslationChunkRepository;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TranslationChunkDegradationService {

    private final TranslationChunkRepository chunkRepository;
    private final int maxDepth;
    private final ObjectMapper objectMapper = JsonMapper.builder().build();

    public TranslationChunkDegradationService(
            TranslationChunkRepository chunkRepository,
            @Value("${fanbook.translation.max-degradation-depth:3}") int maxDepth
    ) {
        this.chunkRepository = chunkRepository;
        this.maxDepth = Math.max(0, maxDepth);
    }

    @Transactional
    public List<ChunkMessage> degrade(Long chunkId) {
        TranslationChunkEntity chunk = chunkRepository.findById(chunkId).orElse(null);
        if (chunk == null || chunk.getStatus() == TranslationChunkStatus.SUPERSEDED || chunk.getDegradationDepth() >= maxDepth) {
            return List.of();
        }
        List<Long> segmentIds = parseSegmentIds(chunk.getSegmentIdsJson());
        if (segmentIds.size() <= 1) {
            return List.of();
        }
        List<List<Long>> groups = split(segmentIds);
        List<ChunkMessage> messages = new ArrayList<>();
        int nextOrder = chunk.getChunkOrder() * 1000;
        for (List<Long> group : groups) {
            TranslationChunkEntity child = new TranslationChunkEntity(
                    chunk.getJob(),
                    chunk.getBook(),
                    chunk.getChapter(),
                    nextOrder++,
                    toJson(group),
                    TranslationChunkStatus.PENDING,
                    chunk.getEstimatedTokens() / groups.size()
            );
            child.attachParent(chunk, chunk.getDegradationDepth() + 1);
            chunkRepository.save(child);
            messages.add(ChunkMessage.start(chunk.getJob().getId(), child.getId()));
        }
        chunk.markSuperseded(
                "chunk_degraded",
                "Chunk was split into " + groups.size() + " smaller retry chunks.",
                OffsetDateTime.now()
        );
        return messages;
    }

    private static List<List<Long>> split(List<Long> segmentIds) {
        if (segmentIds.size() == 2) {
            return segmentIds.stream().map(List::of).toList();
        }
        int midpoint = (segmentIds.size() + 1) / 2;
        return List.of(
                List.copyOf(segmentIds.subList(0, midpoint)),
                List.copyOf(segmentIds.subList(midpoint, segmentIds.size()))
        );
    }

    private List<Long> parseSegmentIds(String segmentIdsJson) {
        try {
            return objectMapper.readValue(segmentIdsJson, new TypeReference<List<Long>>() {
            });
        } catch (Exception exception) {
            return List.of();
        }
    }

    private String toJson(List<Long> ids) {
        try {
            return objectMapper.writeValueAsString(ids);
        } catch (Exception exception) {
            throw new IllegalStateException("Failed to serialize degraded chunk ids.", exception);
        }
    }
}
