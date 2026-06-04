package com.fanbook.translation.infrastructure;

import com.fanbook.translation.application.ChunkMessage;
import com.fanbook.translation.application.TranslationChunkPublisher;
import com.fanbook.translation.config.TranslationMessagingProperties;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;

@Component
public class RabbitTranslationChunkPublisher implements TranslationChunkPublisher {

    private final RabbitTemplate rabbitTemplate;
    private final TranslationMessagingProperties properties;

    public RabbitTranslationChunkPublisher(RabbitTemplate rabbitTemplate, TranslationMessagingProperties properties) {
        this.rabbitTemplate = rabbitTemplate;
        this.properties = properties;
    }

    @Override
    public void publish(ChunkMessage message) {
        rabbitTemplate.convertAndSend(properties.exchange(), properties.routingKey(), message);
    }
}
