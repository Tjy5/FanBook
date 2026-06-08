package com.fanbook.translation.application;

import com.fanbook.ai.infrastructure.OpenAiCompatibleProperties;
import com.fanbook.translation.config.TranslationChunkPlanningProperties;
import com.fanbook.translation.config.TranslationMessagingProperties;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Service
public class TranslationRuntimeSafetyService {

    private static final long LOW_RPM_INTERVAL_SECONDS = 6;

    private final Environment environment;
    private final OpenAiCompatibleProperties aiProperties;
    private final TranslationMessagingProperties messagingProperties;
    private final TranslationChunkPlanningProperties chunkPlanningProperties;
    private final int maxAttemptsPerChunk;

    public TranslationRuntimeSafetyService(
            Environment environment,
            OpenAiCompatibleProperties aiProperties,
            TranslationMessagingProperties messagingProperties,
            TranslationChunkPlanningProperties chunkPlanningProperties,
            @Value("${fanbook.translation.max-attempts-per-chunk:3}") int maxAttemptsPerChunk
    ) {
        this.environment = environment;
        this.aiProperties = aiProperties;
        this.messagingProperties = messagingProperties;
        this.chunkPlanningProperties = chunkPlanningProperties;
        this.maxAttemptsPerChunk = Math.max(1, maxAttemptsPerChunk);
    }

    public TranslationRuntimeProfile activeProfile() {
        return profile(null, null);
    }

    public TranslationRuntimeProfile profile(String requestedProviderName, String requestedModelName) {
        String activeProviderName = activeProviderName();
        String providerName = value(requestedProviderName, activeProviderName);
        String modelName = value(requestedModelName, defaultModelName(providerName));
        boolean providerAvailable = providerName.equalsIgnoreCase(activeProviderName);
        boolean realProvider = !"mock".equalsIgnoreCase(providerName);
        boolean configured = providerAvailable && (!realProvider || configured(providerName));
        String endpoint = endpoint(providerName);
        boolean usesChatCompletions = "openai-compatible".equalsIgnoreCase(providerName)
                && aiProperties.usesChatCompletions();
        String thinkingMode = thinkingMode(providerName);
        long minRequestIntervalSeconds = seconds(aiProperties.minRequestInterval());
        long requestTimeoutSeconds = seconds(aiProperties.requestTimeout());
        List<String> warnings = new ArrayList<>();
        List<String> recommendations = recommendations(realProvider, isDeepSeekLike(providerName, modelName));
        boolean safeToStart = true;

        if (!providerAvailable) {
            warnings.add("Requested provider '" + providerName + "' is not the active backend provider '" + activeProviderName + "'.");
            safeToStart = false;
        }
        if (realProvider && !configured) {
            warnings.add("OpenAI-compatible provider is selected but FANBOOK_AI_API_KEY is not configured.");
            safeToStart = false;
        }
        if (realProvider && !messagingProperties.listenerAutoStartup()) {
            warnings.add("Translation messaging listener auto-startup is disabled; frontend async jobs will not be consumed.");
            safeToStart = false;
        }
        if (realProvider && aiProperties.maxConcurrency() > 1) {
            warnings.add("Provider max concurrency is " + aiProperties.maxConcurrency() + "; use 1 for 60 RPM paid models.");
            safeToStart = false;
        }
        if (realProvider && messagingProperties.concurrency() > 1) {
            warnings.add("Messaging concurrency is " + messagingProperties.concurrency() + "; use 1 for low-RPM paid jobs.");
            safeToStart = false;
        }
        if (realProvider && messagingProperties.prefetch() > 1) {
            warnings.add("Messaging prefetch is " + messagingProperties.prefetch() + "; use 1 for low-RPM paid jobs.");
            safeToStart = false;
        }
        if (realProvider && minRequestIntervalSeconds < LOW_RPM_INTERVAL_SECONDS) {
            warnings.add("Provider minimum request interval is " + minRequestIntervalSeconds + "s; use at least 6s for 60 RPM paid models.");
            safeToStart = false;
        }
        if (realProvider && maxAttemptsPerChunk > 1) {
            warnings.add("Chunk max attempts is " + maxAttemptsPerChunk + "; retries can multiply paid requests.");
        }

        boolean deepSeekLike = isDeepSeekLike(providerName, modelName);
        if (realProvider && deepSeekLike && !usesChatCompletions) {
            warnings.add("DeepSeek-like model is selected but Chat Completions endpoint is not active.");
            safeToStart = false;
        }
        if (realProvider && deepSeekLike && !"disabled".equalsIgnoreCase(thinkingMode)) {
            warnings.add("DeepSeek-like model is selected but thinking mode is not disabled.");
            safeToStart = false;
        }

        return new TranslationRuntimeProfile(
                providerName,
                modelName,
                configured,
                realProvider,
                safeToStart,
                safetyLevel(realProvider, safeToStart, warnings),
                endpoint,
                usesChatCompletions,
                thinkingMode,
                Boolean.TRUE.equals(aiProperties.jsonMode()),
                aiProperties.maxConcurrency(),
                minRequestIntervalSeconds,
                requestTimeoutSeconds,
                messagingProperties.prefetch(),
                messagingProperties.concurrency(),
                messagingProperties.listenerAutoStartup(),
                chunkPlanningProperties.chunkTargetCharacters(),
                chunkPlanningProperties.maxSegmentsPerChunk(),
                maxAttemptsPerChunk,
                List.copyOf(warnings),
                recommendations
        );
    }

    public String activeProviderName() {
        return value(environment.getProperty("fanbook.ai.provider"), "mock");
    }

    private String defaultModelName(String providerName) {
        if ("mock".equalsIgnoreCase(providerName)) {
            return "mock-translator";
        }
        return value(aiProperties.model(), "mock-translator");
    }

    private boolean configured(String providerName) {
        return !"openai-compatible".equalsIgnoreCase(providerName) || StringUtils.hasText(aiProperties.apiKey());
    }

    private String endpoint(String providerName) {
        if (!"openai-compatible".equalsIgnoreCase(providerName)) {
            return "mock";
        }
        if (aiProperties.usesChatCompletions()) {
            return "chat-completions";
        }
        return value(aiProperties.endpoint(), "responses");
    }

    private String thinkingMode(String providerName) {
        if (!"openai-compatible".equalsIgnoreCase(providerName)) {
            return "n/a";
        }
        return value(aiProperties.thinkingMode(), "default");
    }

    private static List<String> recommendations(boolean realProvider, boolean deepSeekLike) {
        if (!realProvider) {
            return List.of();
        }
        List<String> values = new ArrayList<>();
        values.add("Use FANBOOK_AI_MAX_CONCURRENCY=1 for paid low-RPM models.");
        values.add("Use FANBOOK_AI_MIN_REQUEST_INTERVAL=6s for a 60 RPM limit.");
        values.add("Use FANBOOK_TRANSLATION_MESSAGING_PREFETCH=1 and FANBOOK_TRANSLATION_MESSAGING_CONCURRENCY=1 for low-RPM paid jobs.");
        if (deepSeekLike) {
            values.add("Use FANBOOK_AI_ENDPOINT=chat-completions and FANBOOK_AI_THINKING_MODE=disabled for non-thinking DeepSeek translation.");
        }
        return List.copyOf(values);
    }

    private static String safetyLevel(boolean realProvider, boolean safeToStart, List<String> warnings) {
        if (!safeToStart) {
            return "unsafe";
        }
        if (!realProvider) {
            return "mock";
        }
        if (!warnings.isEmpty()) {
            return "warning";
        }
        return "safe";
    }

    private static boolean isDeepSeekLike(String providerName, String modelName) {
        String value = (providerName + " " + modelName).toLowerCase(Locale.ROOT);
        return value.contains("deepseek");
    }

    private static long seconds(Duration duration) {
        return duration == null ? 0 : Math.max(0, duration.toSeconds());
    }

    private static String value(String candidate, String fallback) {
        if (StringUtils.hasText(candidate)) {
            return candidate.trim();
        }
        return fallback;
    }
}
