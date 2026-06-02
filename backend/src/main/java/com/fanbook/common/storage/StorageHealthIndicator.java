package com.fanbook.common.storage;

import java.nio.file.Files;
import java.nio.file.Path;
import org.springframework.boot.health.contributor.Health;
import org.springframework.boot.health.contributor.HealthIndicator;
import org.springframework.stereotype.Component;

@Component("storage")
public class StorageHealthIndicator implements HealthIndicator {

    private final Path root;

    public StorageHealthIndicator(LocalStorageProperties properties) {
        this.root = properties.root().toAbsolutePath().normalize();
    }

    @Override
    public Health health() {
        try {
            Files.createDirectories(root);
            Path probe = root.resolve(".health");
            Files.writeString(probe, "ok");
            Files.deleteIfExists(probe);
            return Health.up().withDetail("root", root.toString()).build();
        } catch (Exception exception) {
            return Health.down(exception).withDetail("root", root.toString()).build();
        }
    }
}
