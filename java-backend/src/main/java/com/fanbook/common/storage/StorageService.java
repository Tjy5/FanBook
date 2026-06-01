package com.fanbook.common.storage;

public interface StorageService {
    StorageObject put(String objectKey, byte[] content);

    byte[] read(String objectKey);
}
