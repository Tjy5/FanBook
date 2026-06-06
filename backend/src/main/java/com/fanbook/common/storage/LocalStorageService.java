package com.fanbook.common.storage;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Service
@EnableConfigurationProperties(LocalStorageProperties.class)
public class LocalStorageService implements StorageService {

    private final Path root;

    public LocalStorageService(LocalStorageProperties properties) {
        this.root = properties.root().toAbsolutePath().normalize();
    }

    @Override
    public StorageObject put(String objectKey, byte[] content) {
        Path target = resolve(objectKey);
        try {
            Files.createDirectories(target.getParent());
            Path temp = Files.createTempFile(target.getParent(), ".fanbook-", ".tmp");
            Files.write(temp, content, StandardOpenOption.TRUNCATE_EXISTING);
            moveIntoPlace(temp, target);
            return new StorageObject(objectKey, content.length);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    @Override
    public StorageObjectContent readObject(String objectKey) {
        try {
            Path target = resolve(objectKey);
            return new StorageObjectContent(objectKey, Files.size(target), Files.readAllBytes(target));
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    @Override
    public boolean exists(String objectKey) {
        return Files.isRegularFile(resolve(objectKey));
    }

    @Override
    public void delete(String objectKey) {
        try {
            Files.deleteIfExists(resolve(objectKey));
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    private Path resolve(String objectKey) {
        if (!StringUtils.hasText(objectKey) || objectKey.contains("\\")) {
            throw new IllegalArgumentException("Object key must be a non-empty slash-delimited relative path.");
        }
        Path relative = Path.of(objectKey).normalize();
        if (relative.isAbsolute() || relative.startsWith("..")) {
            throw new IllegalArgumentException("Object key escapes storage root.");
        }
        Path target = root.resolve(relative).normalize();
        if (!target.startsWith(root)) {
            throw new IllegalArgumentException("Object key escapes storage root.");
        }
        return target;
    }

    private void moveIntoPlace(Path temp, Path target) throws IOException {
        try {
            Files.move(temp, target, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        } catch (IOException atomicMoveFailure) {
            Files.move(temp, target, StandardCopyOption.REPLACE_EXISTING);
        }
    }
}
