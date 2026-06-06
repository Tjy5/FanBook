package com.fanbook.common.storage;

public interface StorageService {
    StorageObject put(String objectKey, byte[] content);

    StorageObjectContent readObject(String objectKey);

    default byte[] read(String objectKey) {
        return readObject(objectKey).content();
    }

    boolean exists(String objectKey);

    void delete(String objectKey);
}
