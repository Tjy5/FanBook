package com.fanbook.e2e;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fanbook.common.lock.BookTranslationLock;
import com.fanbook.testsupport.MinimalEpubFactory;
import com.fanbook.translation.application.TranslationChunkPublisher;
import com.fanbook.translation.application.TranslationJobExecutor;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class FanbookE2eTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:fanbook_e2e;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/e2e-storage");
        registry.add("fanbook.ai.provider", () -> "mock");
    }

    @Autowired
    MockMvc mockMvc;

    private final ObjectMapper objectMapper = JsonMapper.builder().build();

    @Test
    void uploadTranslateAndDownloadArtifacts() throws Exception {
        MockMultipartFile file = new MockMultipartFile(
                "file",
                "demo.epub",
                "application/epub+zip",
                MinimalEpubFactory.create()
        );
        String uploadBody = mockMvc.perform(multipart("/api/books").file(file).param("sourceLanguage", "en"))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        Long bookId = objectMapper.readTree(uploadBody).get("bookId").asLong();

        String jobBody = mockMvc.perform(post("/api/books/" + bookId + "/translation-jobs")
                        .contentType("application/json")
                        .content("{\"providerName\":\"mock\",\"modelName\":\"mock-translator\"}"))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        JsonNode job = objectMapper.readTree(jobBody);

        assertThat(job.get("bookId").asLong()).isEqualTo(bookId);
        waitUntilCompleted(job.get("jobId").asLong());

        mockMvc.perform(get("/api/books/" + bookId + "/exports/zh"))
                .andExpect(status().isOk());
        mockMvc.perform(get("/api/books/" + bookId + "/reports/consistency"))
                .andExpect(status().isOk());
    }

    private void waitUntilCompleted(Long jobId) throws Exception {
        long deadline = System.currentTimeMillis() + 10_000;
        while (System.currentTimeMillis() < deadline) {
            String body = mockMvc.perform(get("/api/translation-jobs/" + jobId))
                    .andExpect(status().isOk())
                    .andReturn().getResponse().getContentAsString();
            String status = objectMapper.readTree(body).get("status").asText();
            if ("COMPLETED".equals(status)) {
                return;
            }
            if ("FAILED".equals(status) || "CANCELED".equals(status)) {
                throw new AssertionError("translation job ended with status " + status);
            }
            Thread.sleep(200);
        }
        throw new AssertionError("translation job did not complete within 10 seconds");
    }

    @TestConfiguration
    static class LockConfig {
        @Bean
        @Primary
        TranslationChunkPublisher executingTranslationChunkPublisher(
                TranslationJobExecutor executor,
                ThreadPoolTaskExecutor translationTaskExecutor
        ) {
            return message -> translationTaskExecutor.execute(() -> executor.runJob(message.jobId()));
        }

        @Bean
        @Primary
        BookTranslationLock inMemoryBookTranslationLock() {
            return new BookTranslationLock() {
                private final Map<Long, Long> locks = new ConcurrentHashMap<>();

                @Override
                public boolean acquire(Long bookId, Long jobId) {
                    return locks.putIfAbsent(bookId, jobId) == null;
                }

                @Override
                public void release(Long bookId, Long jobId) {
                    locks.remove(bookId, jobId);
                }
            };
        }
    }
}
