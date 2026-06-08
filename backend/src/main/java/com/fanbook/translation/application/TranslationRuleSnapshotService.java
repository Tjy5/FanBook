package com.fanbook.translation.application;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.MapperFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fanbook.ai.domain.StructuredTranslationGlossaryItem;
import com.fanbook.ai.domain.TranslationPromptProfile;
import com.fanbook.book.domain.BookEntity;
import com.fanbook.translation.api.StartTranslationRequest;
import com.fanbook.translation.config.TranslationChunkPlanningProperties;
import com.fanbook.translation.config.TranslationPromptProperties;
import com.fanbook.translation.domain.TranslationGlossaryCandidateStatus;
import com.fanbook.translation.domain.TranslationRuleSnapshotEntity;
import com.fanbook.translation.infrastructure.TranslationGlossaryCandidateRepository;
import com.fanbook.translation.infrastructure.TranslationRuleSnapshotRepository;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TranslationRuleSnapshotService {

    public static final String DEFAULT_TARGET_LANGUAGE = "zh";

    private final TranslationRuleSnapshotRepository snapshotRepository;
    private final TranslationGlossaryCandidateRepository candidateRepository;
    private final TranslationChunkPlanningProperties chunkPlanningProperties;
    private final TranslationPromptProperties promptProperties;
    private final TranslationGlossaryMerger glossaryMerger = new TranslationGlossaryMerger();
    private final ObjectMapper objectMapper = JsonMapper.builder()
            .configure(MapperFeature.SORT_PROPERTIES_ALPHABETICALLY, true)
            .configure(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS, true)
            .build();

    public TranslationRuleSnapshotService(
            TranslationRuleSnapshotRepository snapshotRepository,
            TranslationGlossaryCandidateRepository candidateRepository,
            TranslationChunkPlanningProperties chunkPlanningProperties,
            TranslationPromptProperties promptProperties
    ) {
        this.snapshotRepository = snapshotRepository;
        this.candidateRepository = candidateRepository;
        this.chunkPlanningProperties = chunkPlanningProperties;
        this.promptProperties = promptProperties;
    }

    @Transactional
    public TranslationRuleSnapshotEntity capture(BookEntity book, StartTranslationRequest request) {
        TranslationPromptProfile promptProfile = promptProfile(request == null ? null : request.promptProfile());
        TranslationPreservationOptions preservation = TranslationPreservationOptions.defaults();
        List<StructuredTranslationGlossaryItem> glossary = glossaryForSnapshot(book.getId());
        String promptJson = toJson(promptProfile);
        String glossaryJson = toJson(glossary);
        String preservationJson = toJson(preservation);
        String hash = hash(Map.of(
                "targetLanguage", DEFAULT_TARGET_LANGUAGE,
                "promptProfile", promptProfile,
                "glossary", glossary,
                "preservation", preservation
        ));
        return snapshotRepository.findFirstByBookIdAndSnapshotHashOrderByIdDesc(book.getId(), hash)
                .orElseGet(() -> snapshotRepository.save(new TranslationRuleSnapshotEntity(
                        book,
                        hash,
                        DEFAULT_TARGET_LANGUAGE,
                        promptJson,
                        glossaryJson,
                        preservationJson
                )));
    }

    @Transactional(readOnly = true)
    public TranslationRuleSnapshotData dataForJob(com.fanbook.translation.domain.TranslationJobEntity job) {
        TranslationRuleSnapshotEntity snapshot = job.getRuleSnapshot();
        if (snapshot == null) {
            return defaultData();
        }
        return data(snapshot);
    }

    @Transactional(readOnly = true)
    public TranslationRuleSnapshotData dataForBook(BookEntity book) {
        TranslationPromptProfile promptProfile = promptProfile(null);
        TranslationPreservationOptions preservation = TranslationPreservationOptions.defaults();
        List<StructuredTranslationGlossaryItem> glossary = glossaryForSnapshot(book.getId());
        String hash = hash(Map.of(
                "targetLanguage", DEFAULT_TARGET_LANGUAGE,
                "promptProfile", promptProfile,
                "glossary", glossary,
                "preservation", preservation
        ));
        return new TranslationRuleSnapshotData(null, hash, DEFAULT_TARGET_LANGUAGE, promptProfile, preservation, glossary);
    }

    public TranslationRuleSnapshotData data(TranslationRuleSnapshotEntity snapshot) {
        return new TranslationRuleSnapshotData(
                snapshot.getId(),
                snapshot.getSnapshotHash(),
                snapshot.getTargetLanguage(),
                fromJson(snapshot.getPromptProfileJson(), TranslationPromptProfile.class, TranslationPromptProfile.defaults()),
                fromJson(snapshot.getPreservationJson(), TranslationPreservationOptions.class, TranslationPreservationOptions.defaults()),
                glossaryFromJson(snapshot.getGlossaryJson())
        );
    }

    public TranslationRuleSnapshotData defaultData() {
        TranslationPromptProfile promptProfile = promptProfile(null);
        TranslationPreservationOptions preservation = TranslationPreservationOptions.defaults();
        List<StructuredTranslationGlossaryItem> glossary = chunkPlanningProperties.glossary();
        String hash = hash(Map.of(
                "targetLanguage", DEFAULT_TARGET_LANGUAGE,
                "promptProfile", promptProfile,
                "glossary", glossary,
                "preservation", preservation
        ));
        return new TranslationRuleSnapshotData(null, hash, DEFAULT_TARGET_LANGUAGE, promptProfile, preservation, glossary);
    }

    private TranslationPromptProfile promptProfile(StartTranslationRequest.TranslationPromptProfileRequest request) {
        if (request == null) {
            return new TranslationPromptProfile(
                    promptProperties.name(),
                    promptProperties.version(),
                    promptProperties.styleInstruction(),
                    promptProperties.translationInstruction(),
                    promptProperties.reviewInstruction(),
                    promptProperties.analysisInstruction(),
                    promptProperties.preserveFormatting()
            );
        }
        return new TranslationPromptProfile(
                value(request.name(), promptProperties.name()),
                value(request.version(), promptProperties.version()),
                value(request.styleInstruction(), promptProperties.styleInstruction()),
                value(request.translationInstruction(), promptProperties.translationInstruction()),
                value(request.reviewInstruction(), promptProperties.reviewInstruction()),
                value(request.analysisInstruction(), promptProperties.analysisInstruction()),
                request.preserveFormatting() == null ? promptProperties.preserveFormatting() : request.preserveFormatting()
        );
    }

    private List<StructuredTranslationGlossaryItem> glossaryForSnapshot(Long bookId) {
        List<StructuredTranslationGlossaryItem> acceptedCandidates = candidateRepository.findByBookIdAndStatusInOrderByIdAsc(
                        bookId,
                        List.of(TranslationGlossaryCandidateStatus.ACCEPTED)
                ).stream()
                .map(candidate -> new StructuredTranslationGlossaryItem(
                        candidate.getSourceTerm(),
                        candidate.getTargetTerm(),
                        candidate.getCategory(),
                        candidate.getNote()
                ))
                .toList();
        return glossaryMerger.merge(
                chunkPlanningProperties.glossary(),
                acceptedCandidates,
                TranslationGlossaryMerger.MergeMode.FILL_EMPTY
        ).items();
    }

    private List<StructuredTranslationGlossaryItem> glossaryFromJson(String json) {
        try {
            var type = objectMapper.getTypeFactory().constructCollectionType(List.class, StructuredTranslationGlossaryItem.class);
            return List.copyOf(objectMapper.readValue(json, type));
        } catch (Exception exception) {
            return List.of();
        }
    }

    private <T> T fromJson(String json, Class<T> type, T fallback) {
        try {
            return objectMapper.readValue(json, type);
        } catch (Exception exception) {
            return fallback;
        }
    }

    private String toJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Failed to serialize translation rule snapshot.", exception);
        }
    }

    private String hash(Object value) {
        try {
            String json = toJson(value);
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(json.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is not available.", exception);
        }
    }

    private static String value(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value.trim();
    }
}
