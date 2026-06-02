package com.fanbook.ai.infrastructure;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fanbook.ai.domain.AiTranslationProvider;
import com.fanbook.ai.domain.StructuredTranslationRequest;
import com.fanbook.ai.domain.StructuredTranslationResult;
import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
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
            Translate the source segments into the target language.
            Return JSON only with shape {"items":[{"segmentId":number,"translatedText":string}]}.
            Preserve every input segmentId exactly once.
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
    public StructuredTranslationResult translateChunk(StructuredTranslationRequest request) {
        requireApiKey();
        acquirePermit();
        try {
            Map<String, Object> payload = Map.of(
                    "model", properties.model(),
                    "instructions", STRUCTURED_OUTPUT_INSTRUCTIONS,
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
            return new StructuredTranslationResult(parsed.items(), name(), properties.model());
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
