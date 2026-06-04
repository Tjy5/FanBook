package com.fanbook.translation.config;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.amqp.core.Queue;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

@SpringBootTest
class TranslationRabbitConfigTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:rabbit_config;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.ai.provider", () -> "mock");
    }

    @Autowired
    TranslationMessagingProperties properties;

    @Autowired
    Queue translationChunkQueue;

    @Test
    void declaresChunkQueueWithConfiguredName() {
        assertThat(properties.chunkQueue()).isEqualTo("translation.chunk.queue");
        assertThat(translationChunkQueue.getName()).isEqualTo("translation.chunk.queue");
        assertThat(translationChunkQueue.isDurable()).isTrue();
    }
}
