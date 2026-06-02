package com.fanbook.ai.infrastructure;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "fanbook.ai")
public record OpenAiCompatibleProperties(
        String baseUrl,
        String apiKey,
        String model,
        Duration requestTimeout,
        int maxConcurrency
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
    }
}
