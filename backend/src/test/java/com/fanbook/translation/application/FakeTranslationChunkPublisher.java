package com.fanbook.translation.application;

import java.util.ArrayList;
import java.util.List;
import java.util.function.Consumer;

public class FakeTranslationChunkPublisher implements TranslationChunkPublisher {

    private final List<ChunkMessage> messages = new ArrayList<>();
    private Consumer<ChunkMessage> onPublish = message -> {
    };

    @Override
    public void publish(ChunkMessage message) {
        messages.add(message);
        onPublish.accept(message);
    }

    public List<ChunkMessage> messages() {
        return List.copyOf(messages);
    }

    public void onPublish(Consumer<ChunkMessage> onPublish) {
        this.onPublish = onPublish == null ? message -> {
        } : onPublish;
    }

    public void clear() {
        messages.clear();
        onPublish = message -> {
        };
    }
}
