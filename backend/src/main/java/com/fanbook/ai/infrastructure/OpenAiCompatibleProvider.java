package com.fanbook.ai.infrastructure;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fanbook.ai.domain.AiTranslationProvider;
import com.fanbook.ai.domain.StructuredGlossaryAnalysisRequest;
import com.fanbook.ai.domain.StructuredGlossaryAnalysisResult;
import com.fanbook.ai.domain.StructuredTranslationReviewRequest;
import com.fanbook.ai.domain.StructuredTranslationRequest;
import com.fanbook.ai.domain.StructuredTranslationResult;
import com.fanbook.ai.domain.TranslationPromptProfile;
import com.fanbook.translation.application.TranslationPreservationOptions;
import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Semaphore;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
@ConditionalOnProperty(name = "fanbook.ai.provider", havingValue = "openai-compatible")
public class OpenAiCompatibleProvider implements AiTranslationProvider {

    private static final String STRUCTURED_OUTPUT_INSTRUCTIONS = """
            Translate the source segments into natural, publication-quality target-language prose.
            Return JSON only with shape {"items":[{"segmentId":number,"translatedText":string}]}.
            Preserve every input segmentId exactly once.
            Translate only the request items; use context only for terminology, style, names, pronouns, and continuity.
            Use glossary entries as terminology/name constraints. If targetTerm is present, use it consistently.
            Do not merge, split, omit, or reorder segments.
            Keep each translatedText aligned to exactly one source segment.
            Preserve numbers, names, inline markers, links, punctuation intent, and formatting hints.
            Maintain consistent terminology, character names, tone, and narrative voice within the chapter.
            """;
    private static final String REVIEW_INSTRUCTIONS = """
            Review existing target-language book translations and fix only concrete quality issues.
            Return JSON only with shape {"items":[{"segmentId":number,"translatedText":string}]}.
            Preserve every input segmentId exactly once.
            Do not retranslate from scratch when the current translation is acceptable.
            Use the current translation as the base text; make the smallest correction that resolves the listed warnings.
            Preserve meaning, names, numbers, terminology, tone, punctuation intent, and inline markers.
            Use glossary entries as terminology/name constraints. If targetTerm is present, use it consistently.
            Do not merge, split, omit, or reorder segments.
            If a segment has no obvious problem beyond the warning signal, return its current translation unchanged.
            """;
    private static final String ANALYSIS_INSTRUCTIONS = """
            Analyze source-language book segments and extract only true proper nouns or book-specific terminology.
            Return JSON only with shape {"candidates":[{"sourceTerm":string,"targetTerm":string|null,"category":string,"note":string,"segmentId":number|null}]}.
            Prefer people, places, organizations, families, unique fictional concepts, special objects, and recurring named entities.
            Ignore generic common nouns, generic titles, relationship words, and ordinary dictionary terms.
            Keep sourceTerm boundaries precise and do not include surrounding titles or descriptions unless they are part of the name.
            """;

    private final RestClient restClient;
    private final ObjectMapper objectMapper;
    private final OpenAiCompatibleProperties properties;
    private final Semaphore semaphore;

    @Autowired
    public OpenAiCompatibleProvider(OpenAiCompatibleProperties properties) {
        this(RestClient.builder(), JsonMapper.builder().build(), properties);
    }

    OpenAiCompatibleProvider(
            RestClient.Builder builder,
            ObjectMapper objectMapper,
            OpenAiCompatibleProperties properties
    ) {
        this.restClient = builder.baseUrl(trimTrailingSlash(properties.baseUrl())).build();
        this.objectMapper = objectMapper;
        this.properties = properties;
        this.semaphore = new Semaphore(properties.maxConcurrency());
    }

    @Override
    public String name() {
        return "openai-compatible";
    }

    @Override
    public StructuredTranslationResult translateChunk(StructuredTranslationRequest request, String modelName) {
        return sendStructuredTranslationRequest(instructions(STRUCTURED_OUTPUT_INSTRUCTIONS, request.promptProfile(), request.preservation(), "translation"), request, modelName);
    }

    @Override
    public StructuredTranslationResult reviewTranslations(StructuredTranslationReviewRequest request, String modelName) {
        return sendStructuredTranslationRequest(instructions(REVIEW_INSTRUCTIONS, request.promptProfile(), request.preservation(), "review"), request, modelName);
    }

    @Override
    public StructuredGlossaryAnalysisResult analyzeGlossary(StructuredGlossaryAnalysisRequest request, String modelName) {
        requireApiKey();
        acquirePermit();
        try {
            String resolvedModelName = modelName == null || modelName.isBlank() ? properties.model() : modelName;
            Map<String, Object> payload = Map.of(
                    "model", resolvedModelName,
                    "instructions", instructions(ANALYSIS_INSTRUCTIONS, request.promptProfile(), request.preservation(), "analysis"),
                    "input", objectMapper.writeValueAsString(request)
            );
            String body = restClient.post()
                    .uri("/responses")
                    .header(HttpHeaders.AUTHORIZATION, "Bearer " + properties.apiKey())
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(payload)
                    .retrieve()
                    .body(String.class);
            StructuredGlossaryAnalysisResult parsed = objectMapper.readValue(outputText(body), StructuredGlossaryAnalysisResult.class);
            return new StructuredGlossaryAnalysisResult(parsed.candidates(), name(), resolvedModelName);
        } catch (FanbookException exception) {
            throw exception;
        } catch (Exception exception) {
            throw new FanbookException(
                    ErrorCode.PROVIDER_REQUEST_FAILED,
                    HttpStatus.BAD_GATEWAY,
                    exception.getMessage()
            );
        } finally {
            semaphore.release();
        }
    }

    private StructuredTranslationResult sendStructuredTranslationRequest(String instructions, Object request, String modelName) {
        requireApiKey();
        acquirePermit();
        try {
            String resolvedModelName = modelName == null || modelName.isBlank() ? properties.model() : modelName;
            Map<String, Object> payload = Map.of(
                    "model", resolvedModelName,
                    "instructions", instructions,
                    "input", objectMapper.writeValueAsString(request)
            );
            String body = restClient.post()
                    .uri("/responses")
                    .header(HttpHeaders.AUTHORIZATION, "Bearer " + properties.apiKey())
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(payload)
                    .retrieve()
                    .body(String.class);
            StructuredTranslationResult parsed = objectMapper.readValue(outputText(body), StructuredTranslationResult.class);
            return new StructuredTranslationResult(parsed.items(), name(), resolvedModelName);
        } catch (FanbookException exception) {
            throw exception;
        } catch (Exception exception) {
            throw new FanbookException(
                    ErrorCode.PROVIDER_REQUEST_FAILED,
                    HttpStatus.BAD_GATEWAY,
                    exception.getMessage()
            );
        } finally {
            semaphore.release();
        }
    }

    private static String instructions(
            String base,
            TranslationPromptProfile profile,
            TranslationPreservationOptions preservation,
            String task
    ) {
        TranslationPromptProfile safeProfile = profile == null ? TranslationPromptProfile.defaults() : profile;
        List<String> parts = new ArrayList<>();
        parts.add(base.strip());
        if (!safeProfile.styleInstruction().isBlank()) {
            parts.add("Style profile:\n" + safeProfile.styleInstruction());
        }
        String taskInstruction = switch (task) {
            case "review" -> safeProfile.reviewInstruction();
            case "analysis" -> safeProfile.analysisInstruction();
            default -> safeProfile.translationInstruction();
        };
        if (!taskInstruction.isBlank()) {
            parts.add("Task-specific profile instructions:\n" + taskInstruction);
        }
        if (safeProfile.preserveFormatting()) {
            parts.add("Preservation rules:\n" + preservationInstructions(preservation));
        }
        return String.join("\n\n", parts);
    }

    private static String preservationInstructions(TranslationPreservationOptions preservation) {
        TranslationPreservationOptions options = preservation == null ? TranslationPreservationOptions.defaults() : preservation;
        List<String> rules = new ArrayList<>();
        if (options.urls()) {
            rules.add("Preserve URLs exactly.");
        }
        if (options.emails()) {
            rules.add("Preserve email-like strings exactly.");
        }
        if (options.footnoteMarkers()) {
            rules.add("Preserve footnote and reference markers such as [1], (1), and superscript-like markers.");
        }
        if (options.inlineMarkup()) {
            rules.add("Preserve inline markup-like tags and attributes exactly while translating surrounding natural language.");
        }
        if (options.listNumbering()) {
            rules.add("Preserve list numbering and bullet markers.");
        }
        if (options.codeLikeSpans()) {
            rules.add("Preserve formula-like or code-like spans exactly unless they contain ordinary natural language.");
        }
        return rules.isEmpty() ? "Preserve book formatting and non-natural-language markers." : String.join("\n", rules);
    }

    private void requireApiKey() {
        if (properties.apiKey() == null || properties.apiKey().isBlank()) {
            throw new FanbookException(
                    ErrorCode.PROVIDER_NOT_CONFIGURED,
                    HttpStatus.INTERNAL_SERVER_ERROR,
                    "OpenAI-compatible API key is not configured."
            );
        }
    }

    private void acquirePermit() {
        try {
            semaphore.acquire();
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new FanbookException(
                    ErrorCode.PROVIDER_REQUEST_FAILED,
                    HttpStatus.INTERNAL_SERVER_ERROR,
                    "Interrupted while waiting for provider concurrency permit."
            );
        }
    }

    private String outputText(String body) throws Exception {
        JsonNode root = objectMapper.readTree(body);
        JsonNode directOutputText = root.get("output_text");
        if (directOutputText != null && directOutputText.isTextual()) {
            return directOutputText.asText();
        }

        JsonNode output = root.path("output");
        if (output.isArray()) {
            for (JsonNode item : output) {
                JsonNode content = item.path("content");
                if (content.isArray()) {
                    for (JsonNode part : content) {
                        JsonNode text = part.get("text");
                        if (text != null && text.isTextual()) {
                            return text.asText();
                        }
                    }
                }
            }
        }

        throw new FanbookException(
                ErrorCode.STRUCTURED_OUTPUT_INVALID,
                HttpStatus.BAD_GATEWAY,
                "Provider response does not contain output text."
        );
    }

    private static String trimTrailingSlash(String value) {
        if (value == null || value.isBlank()) {
            return "https://api.openai.com/v1";
        }
        return value.endsWith("/") ? value.substring(0, value.length() - 1) : value;
    }
}
