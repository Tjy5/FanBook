package com.fanbook.translation.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "fanbook.translation.messaging")
public record TranslationMessagingProperties(
        String exchange,
        String chunkQueue,
        String retryQueue,
        String deadLetterQueue,
        String routingKey,
        int prefetch,
        int concurrency,
        boolean listenerAutoStartup
) {
}
