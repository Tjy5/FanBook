package com.fanbook.common.storage;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.boot.health.contributor.Status;

class StorageHealthIndicatorTest {

    @TempDir
    Path tempDir;

    @Test
    void reportsUpWhenStorageRootIsWritable() {
        StorageHealthIndicator indicator = new StorageHealthIndicator(new LocalStorageProperties(tempDir));

        assertThat(indicator.health().getStatus()).isEqualTo(Status.UP);
    }
}
