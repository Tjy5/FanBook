package com.fanbook.translation.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static com.fanbook.testsupport.SecurityMockMvcSupport.csrfToken;
import static com.fanbook.testsupport.SecurityMockMvcSupport.member;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fanbook.book.application.BookApplicationService;
import com.fanbook.testsupport.MinimalEpubFactory;
import com.fanbook.translation.api.StartTranslationRequest;
import com.fanbook.translation.domain.TranslationChunkStatus;
import com.fanbook.translation.infrastructure.TranslationChunkRepository;
import com.fanbook.translation.infrastructure.TranslationJobRepository;
import java.time.OffsetDateTime;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class TranslationResumeMessagingTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:translation_resume_messaging;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/translation-resume-messaging-storage");
        registry.add("fanbook.ai.provider", () -> "mock");
    }

    @Autowired
    BookApplicationService bookApplicationService;

    @Autowired
    TranslationJobService translationJobService;

    @Autowired
    TranslationResumeService resumeService;

    @Autowired
    TranslationChunkRepository chunkRepository;

    @Autowired
    TranslationJobRepository jobRepository;

    @Autowired
    FakeTranslationChunkPublisher publisher;

    @Autowired
    MockMvc mockMvc;

    @BeforeEach
    void clearPublisher() {
        publisher.clear();
    }

    @Test
    void resumeFailedJobQueuesChunksAfterCommit() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "mock-translator"),
                "system"
        );
        markJobFailedWithRunningChunk(job.jobId());

        var resumed = resumeService.resume(book.bookId());

        assertThat(resumed.status()).isEqualTo("QUEUED");
        assertThat(chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId()))
                .allSatisfy(chunk -> assertThat(chunk.getStatus()).isEqualTo(TranslationChunkStatus.PENDING));
        assertThat(publisher.messages()).hasSize(1);
        assertThat(publisher.messages().getFirst().dispatchReason()).isEqualTo("START");
    }

    @Test
    void resumeRejectsNonStaleRunningJob() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "mock-translator"),
                "system"
        );
        var jobEntity = jobRepository.findById(job.jobId()).orElseThrow();
        jobEntity.markRunning(OffsetDateTime.now());
        jobRepository.saveAndFlush(jobEntity);

        assertThatThrownBy(() -> resumeService.resume(book.bookId()))
                .hasMessageContaining("still running");
        assertThat(publisher.messages()).isEmpty();
    }

    @Test
    void controllerResumePublishesEachChunkOnlyOnce() throws Exception {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "mock-translator"),
                "system"
        );
        markJobFailedWithRunningChunk(job.jobId());

        mockMvc.perform(post("/api/books/" + book.bookId() + "/translation-jobs/resume").with(member()).with(csrfToken()))
                .andExpect(status().isOk());

        assertThat(publisher.messages()).hasSize(1);
    }

    private void markJobFailedWithRunningChunk(Long jobId) {
        var jobEntity = jobRepository.findById(jobId).orElseThrow();
        jobEntity.markFailed("process interrupted", OffsetDateTime.now());
        jobRepository.saveAndFlush(jobEntity);
        var chunk = chunkRepository.findByJobIdOrderByChunkOrderAsc(jobId).getFirst();
        chunk.markRunning(OffsetDateTime.now());
        chunkRepository.saveAndFlush(chunk);
    }

    @TestConfiguration
    static class PublisherConfig {
        @Bean
        @Primary
        FakeTranslationChunkPublisher fakeTranslationChunkPublisher() {
            return new FakeTranslationChunkPublisher();
        }
    }
}
