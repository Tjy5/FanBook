package com.fanbook.common.storage;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class LocalStorageServiceTest {

    @TempDir
    Path tempDir;

    @Test
    void storesAndReadsBytesByObjectKey() throws Exception {
        LocalStorageService storage = new LocalStorageService(new LocalStorageProperties(tempDir));

        StorageObject saved = storage.put("books/1/source.epub", "hello".getBytes(StandardCharsets.UTF_8));

        assertThat(saved.objectKey()).isEqualTo("books/1/source.epub");
        assertThat(Files.exists(tempDir.resolve("books/1/source.epub"))).isTrue();
        assertThat(storage.exists("books/1/source.epub")).isTrue();
        assertThat(storage.readObject("books/1/source.epub").sizeBytes()).isEqualTo(5);
        assertThat(storage.read("books/1/source.epub")).isEqualTo("hello".getBytes(StandardCharsets.UTF_8));
    }

    @Test
    void rejectsObjectKeysThatEscapeRoot() {
        LocalStorageService storage = new LocalStorageService(new LocalStorageProperties(tempDir));

        assertThatThrownBy(() -> storage.put("../outside.epub", "bad".getBytes(StandardCharsets.UTF_8)))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> storage.put("books\\1\\source.epub", "bad".getBytes(StandardCharsets.UTF_8)))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void deletesObjectsByKey() {
        LocalStorageService storage = new LocalStorageService(new LocalStorageProperties(tempDir));
        storage.put("books/1/source.epub", "hello".getBytes(StandardCharsets.UTF_8));

        storage.delete("books/1/source.epub");

        assertThat(storage.exists("books/1/source.epub")).isFalse();
    }
}
