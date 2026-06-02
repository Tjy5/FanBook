package com.fanbook.common.storage;

import java.nio.file.Path;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "fanbook.storage")
public record LocalStorageProperties(Path root) {
}
