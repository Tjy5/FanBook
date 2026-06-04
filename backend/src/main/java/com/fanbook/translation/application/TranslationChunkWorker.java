package com.fanbook.translation.application;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fanbook.ai.application.ProviderFactory;
import com.fanbook.ai.application.StructuredTranslationValidator;
import com.fanbook.ai.domain.StructuredTranslationItem;
import com.fanbook.ai.domain.StructuredTranslationRequest;
import com.fanbook.ai.domain.StructuredTranslationSourceItem;
import com.fanbook.book.domain.SegmentEntity;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import com.fanbook.translation.domain.TranslationChunkEntity;
import com.fanbook.translation.infrastructure.TranslationChunkRepository;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TranslationChunkWorker {

    private final TranslationChunkRepository chunkRepository;
    private final SegmentRepository segmentRepository;
    private final ProviderFactory providerFactory;
    private final StructuredTranslationValidator validator;
    private final ObjectMapper objectMapper = JsonMapper.builder().build();

    public TranslationChunkWorker(
            TranslationChunkRepository chunkRepository,
            SegmentRepository segmentRepository,
            ProviderFactory providerFactory,
            StructuredTranslationValidator validator
    ) {
        this.chunkRepository = chunkRepository;
        this.segmentRepository = segmentRepository;
        this.providerFactory = providerFactory;
        this.validator = validator;
    }

    @Transactional
    public void execute(Long chunkId) {
        TranslationChunkEntity chunk = chunkRepository.findById(chunkId)
                .orElseThrow(() -> notFound("Translation chunk '" + chunkId + "' was not found."));
        List<Long> segmentIds = parseSegmentIds(chunk.getSegmentIdsJson());
        List<SegmentEntity> segments = orderedSegments(segmentIds);
        StructuredTranslationRequest request = buildRequest(chunk, segmentIds, segments);
        var provider = providerFactory.getProvider(chunk.getJob().getProviderName());
        var result = provider.translateChunk(request, chunk.getJob().getModelName());
        validator.validate(segmentIds, result);

        Map<Long, String> translatedById = result.items().stream()
                .collect(Collectors.toMap(StructuredTranslationItem::segmentId, StructuredTranslationItem::translatedText));
        for (SegmentEntity segment : segments) {
            segment.markTranslated(translatedById.get(segment.getId()));
        }
        segmentRepository.saveAll(segments);
    }

    private StructuredTranslationRequest buildRequest(
            TranslationChunkEntity chunk,
            List<Long> segmentIds,
            List<SegmentEntity> segments
    ) {
        Map<Long, SegmentEntity> segmentById = segments.stream()
                .collect(Collectors.toMap(SegmentEntity::getId, Function.identity()));
        List<StructuredTranslationSourceItem> items = segmentIds.stream()
                .map(id -> {
                    SegmentEntity segment = segmentById.get(id);
                    if (segment == null) {
                        throw new FanbookException(
                                ErrorCode.STRUCTURED_OUTPUT_INVALID,
                                HttpStatus.INTERNAL_SERVER_ERROR,
                                "Missing segment '" + id + "' for translation chunk '" + chunk.getId() + "'."
                        );
                    }
                    return new StructuredTranslationSourceItem(id, segment.getSourceText());
                })
                .toList();
        SegmentEntity first = segmentById.get(segmentIds.getFirst());
        return new StructuredTranslationRequest(
                first.getBook().getSourceLanguage(),
                "zh",
                first.getBook().getTitle(),
                first.getChapter().getTitle(),
                items
        );
    }

    private List<SegmentEntity> orderedSegments(List<Long> segmentIds) {
        Map<Long, SegmentEntity> segmentById = segmentRepository.findAllById(segmentIds).stream()
                .collect(Collectors.toMap(SegmentEntity::getId, Function.identity()));
        return segmentIds.stream()
                .map(id -> requireSegment(segmentById, id))
                .toList();
    }

    private SegmentEntity requireSegment(Map<Long, SegmentEntity> segmentById, Long segmentId) {
        SegmentEntity segment = segmentById.get(segmentId);
        if (segment == null) {
            throw new FanbookException(
                    ErrorCode.STRUCTURED_OUTPUT_INVALID,
                    HttpStatus.INTERNAL_SERVER_ERROR,
                    "Missing segment '" + segmentId + "' for translation chunk."
            );
        }
        return segment;
    }

    private List<Long> parseSegmentIds(String segmentIdsJson) {
        try {
            return objectMapper.readValue(segmentIdsJson, new TypeReference<List<Long>>() {
            });
        } catch (Exception exception) {
            throw new FanbookException(
                    ErrorCode.STRUCTURED_OUTPUT_INVALID,
                    HttpStatus.INTERNAL_SERVER_ERROR,
                    "Invalid chunk segment id JSON."
            );
        }
    }

    private FanbookException notFound(String message) {
        return new FanbookException(ErrorCode.TRANSLATION_JOB_NOT_FOUND, HttpStatus.NOT_FOUND, message);
    }
}
