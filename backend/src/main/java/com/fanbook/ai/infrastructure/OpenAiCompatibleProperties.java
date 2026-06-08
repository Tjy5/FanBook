package com.fanbook.ai.infrastructure;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "fanbook.ai")
public record OpenAiCompatibleProperties(
        String baseUrl,
        String apiKey,
        String model,
        Duration requestTimeout,
        int maxConcurrency,
        String endpoint,
        Duration minRequestInterval,
        String thinkingMode,
        Boolean jsonMode
) {
    public OpenAiCompatibleProperties {
        if (baseUrl == null || baseUrl.isBlank()) {
            baseUrl = "https://api.openai.com/v1";
        }
        if (model == null || model.isBlank()) {
            model = "gpt-4o-mini";
        }
        if (requestTimeout == null) {
            requestTimeout = Duration.ofSeconds(90);
        }
        if (maxConcurrency < 1) {
            maxConcurrency = 1;
        }
        if (endpoint == null || endpoint.isBlank()) {
            endpoint = isChatCompletionsUrl(baseUrl) ? "chat-completions" : "responses";
        }
        if (minRequestInterval == null || minRequestInterval.isNegative()) {
            minRequestInterval = Duration.ZERO;
        }
        if (thinkingMode == null) {
            thinkingMode = "";
        } else {
            thinkingMode = thinkingMode.trim();
        }
        if (jsonMode == null) {
            jsonMode = true;
        }
    }

    public boolean usesChatCompletions() {
        return "chat-completions".equalsIgnoreCase(endpoint)
                || isChatCompletionsUrl(baseUrl);
    }

    private static boolean isChatCompletionsUrl(String value) {
        return value != null && value.toLowerCase().endsWith("/chat/completions");
    }
}
