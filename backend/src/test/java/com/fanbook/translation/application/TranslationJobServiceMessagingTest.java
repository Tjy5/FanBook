package com.fanbook.translation.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fanbook.book.application.BookApplicationService;
import com.fanbook.testsupport.MinimalEpubFactory;
import com.fanbook.translation.api.StartTranslationRequest;
import com.fanbook.translation.infrastructure.ActiveTranslationSessionRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

@SpringBootTest
class TranslationJobServiceMessagingTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:job_messaging;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/job-messaging-storage");
        registry.add("fanbook.ai.provider", () -> "mock");
    }

    @Autowired
    BookApplicationService bookApplicationService;

    @Autowired
    TranslationJobService translationJobService;

    @Autowired
    ActiveTranslationSessionRepository activeSessionRepository;

    @Autowired
    FakeTranslationChunkPublisher publisher;

    @BeforeEach
    void clearPublisher() {
        publisher.clear();
    }

    @Test
    void startCreatesActiveSessionAndPublishesChunksAfterCommit() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");

        var job = translationJobService.start(book.bookId(), new StartTranslationRequest("mock", "mock-translator"), "system");

        assertThat(activeSessionRepository.findById(book.bookId())).isPresent();
        assertThat(publisher.messages()).allSatisfy(message -> assertThat(message.jobId()).isEqualTo(job.jobId()));
        assertThat(publisher.messages()).isNotEmpty();
    }

    @Test
    void startRejectsSecondActiveJobForSameBook() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        translationJobService.start(book.bookId(), new StartTranslationRequest("mock", "mock-translator"), "system");

        assertThatThrownBy(() -> translationJobService.start(book.bookId(), new StartTranslationRequest("mock", "mock-translator"), "system"))
                .hasMessageContaining("already has active translation");
    }

    @TestConfiguration
    static class MessagingConfig {
        @Bean
        @Primary
        FakeTranslationChunkPublisher fakeTranslationChunkPublisher() {
            return new FakeTranslationChunkPublisher();
        }
    }
}
