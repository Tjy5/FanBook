package com.fanbook.translation.application;

import java.util.ArrayList;
import java.util.List;

public class FakeTranslationChunkPublisher implements TranslationChunkPublisher {

    private final List<ChunkMessage> messages = new ArrayList<>();

    @Override
    public void publish(ChunkMessage message) {
        messages.add(message);
    }

    public List<ChunkMessage> messages() {
        return List.copyOf(messages);
    }

    public void clear() {
        messages.clear();
    }
}
