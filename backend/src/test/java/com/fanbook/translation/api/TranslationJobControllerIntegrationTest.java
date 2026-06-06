package com.fanbook.translation.api;

import static org.assertj.core.api.Assertions.assertThat;
import static com.fanbook.testsupport.SecurityMockMvcSupport.csrfToken;
import static com.fanbook.testsupport.SecurityMockMvcSupport.member;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fanbook.common.lock.BookTranslationLock;
import com.fanbook.testsupport.MinimalEpubFactory;
import com.fanbook.translation.application.TranslationChunkPublisher;
import com.fanbook.translation.infrastructure.TranslationChunkRepository;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class TranslationJobControllerIntegrationTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:translation_job_controller;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/translation-job-controller-storage");
    }

    @Autowired
    MockMvc mockMvc;

    private final ObjectMapper objectMapper = JsonMapper.builder().build();

    @Autowired
    TranslationChunkRepository chunkRepository;

    @Test
    void createsAndReadsQueuedTranslationJob() throws Exception {
        MockMultipartFile file = new MockMultipartFile("file", "demo.epub", "application/epub+zip", MinimalEpubFactory.create());
        String uploadBody = mockMvc.perform(multipart("/api/books").file(file).param("sourceLanguage", "en").with(member()).with(csrfToken()))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        Long bookId = objectMapper.readTree(uploadBody).get("bookId").asLong();

        String jobBody = mockMvc.perform(post("/api/books/" + bookId + "/translation-jobs")
                        .with(member())
                        .with(csrfToken())
                        .contentType("application/json")
                        .content("{\"providerName\":\"mock\",\"modelName\":\"mock-translator\"}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.bookId").value(bookId))
                .andExpect(jsonPath("$.status").value("QUEUED"))
                .andReturn().getResponse().getContentAsString();
        Long jobId = objectMapper.readTree(jobBody).get("jobId").asLong();

        assertThat(chunkRepository.findByJobIdOrderByChunkOrderAsc(jobId)).hasSize(1);
        String readBody = mockMvc.perform(get("/api/translation-jobs/" + jobId).with(member()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.jobId").value(jobId))
                .andReturn().getResponse().getContentAsString();
        assertThat(Set.of("QUEUED", "RUNNING", "COMPLETED")).contains(objectMapper.readTree(readBody).get("status").asText());
    }

    @TestConfiguration
    static class LockConfig {
        @Bean
        @Primary
        TranslationChunkPublisher noopTranslationChunkPublisher() {
            return message -> {
            };
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
