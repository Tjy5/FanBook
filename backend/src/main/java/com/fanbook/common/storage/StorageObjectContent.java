package com.fanbook.common.storage;

public record StorageObjectContent(String objectKey, long sizeBytes, byte[] content) {

    public StorageObjectContent {
        content = content.clone();
    }

    @Override
    public byte[] content() {
        return content.clone();
    }
}
