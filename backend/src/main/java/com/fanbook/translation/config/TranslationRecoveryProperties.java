package com.fanbook.translation.config;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "fanbook.translation.recovery")
public record TranslationRecoveryProperties(
        Duration chunkLease,
        Duration scanDelay,
        Duration staleJobThreshold
) {
}
