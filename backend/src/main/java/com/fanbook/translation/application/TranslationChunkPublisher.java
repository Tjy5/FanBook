package com.fanbook.translation.application;

import java.util.List;

public interface TranslationChunkPublisher {
    void publish(ChunkMessage message);

    default void publishAll(List<ChunkMessage> messages) {
        messages.forEach(this::publish);
    }
}
