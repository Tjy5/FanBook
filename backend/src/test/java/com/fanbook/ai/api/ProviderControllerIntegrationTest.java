package com.fanbook.ai.api;

import static com.fanbook.testsupport.SecurityMockMvcSupport.member;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class ProviderControllerIntegrationTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:provider_controller;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/provider-controller-storage");
        registry.add("fanbook.ai.provider", () -> "openai-compatible");
        registry.add("fanbook.ai.api-key", () -> "test-key");
        registry.add("fanbook.ai.model", () -> "gpt-4o");
        registry.add("fanbook.ai.max-concurrency", () -> 4);
        registry.add("fanbook.ai.endpoint", () -> "chat-completions");
        registry.add("fanbook.ai.thinking-mode", () -> "disabled");
        registry.add("fanbook.ai.min-request-interval", () -> "2s");
        registry.add("fanbook.ai.request-timeout", () -> "120s");
        registry.add("fanbook.translation.messaging.prefetch", () -> 3);
        registry.add("fanbook.translation.messaging.concurrency", () -> 2);
        registry.add("fanbook.translation.messaging.listener-auto-startup", () -> false);
        registry.add("fanbook.translation.chunk-target-characters", () -> 2500);
        registry.add("fanbook.translation.max-segments-per-chunk", () -> 16);
        registry.add("fanbook.translation.max-attempts-per-chunk", () -> 2);
    }

    @Autowired
    MockMvc mockMvc;

    @Test
    void listsConfiguredProviderProfiles() throws Exception {
        mockMvc.perform(get("/api/providers").with(member()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.default_profile_name").value("openai-compatible"))
                .andExpect(jsonPath("$.providers[0].profile_name").value("openai-compatible"))
                .andExpect(jsonPath("$.providers[0].provider_name").value("openai-compatible"))
                .andExpect(jsonPath("$.providers[0].default_model_name").value("gpt-4o"))
                .andExpect(jsonPath("$.providers[0].configured").value(true))
                .andExpect(jsonPath("$.providers[0].global_max_concurrency").value(4))
                .andExpect(jsonPath("$.providers[0].per_chapter_concurrency").value(1))
                .andExpect(jsonPath("$.providers[0].is_default").value(true))
                .andExpect(jsonPath("$.providers[0].endpoint").value("chat-completions"))
                .andExpect(jsonPath("$.providers[0].uses_chat_completions").value(true))
                .andExpect(jsonPath("$.providers[0].thinking_mode").value("disabled"))
                .andExpect(jsonPath("$.providers[0].json_mode").value(true))
                .andExpect(jsonPath("$.providers[0].min_request_interval_seconds").value(2))
                .andExpect(jsonPath("$.providers[0].request_timeout_seconds").value(120))
                .andExpect(jsonPath("$.providers[0].messaging_prefetch").value(3))
                .andExpect(jsonPath("$.providers[0].messaging_concurrency").value(2))
                .andExpect(jsonPath("$.providers[0].messaging_listener_auto_startup").value(false))
                .andExpect(jsonPath("$.providers[0].chunk_target_characters").value(2500))
                .andExpect(jsonPath("$.providers[0].max_segments_per_chunk").value(16))
                .andExpect(jsonPath("$.providers[0].max_attempts_per_chunk").value(2))
                .andExpect(jsonPath("$.providers[0].paid_safety_level").value("unsafe"))
                .andExpect(jsonPath("$.providers[0].api_key").doesNotExist())
                .andExpect(jsonPath("$.providers[0].base_url").doesNotExist());
    }
}
