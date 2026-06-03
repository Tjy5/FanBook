package com.fanbook.ai.api;

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
    }

    @Autowired
    MockMvc mockMvc;

    @Test
    void listsConfiguredProviderProfiles() throws Exception {
        mockMvc.perform(get("/api/providers"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.default_profile_name").value("openai-compatible"))
                .andExpect(jsonPath("$.providers[0].profile_name").value("openai-compatible"))
                .andExpect(jsonPath("$.providers[0].provider_name").value("openai-compatible"))
                .andExpect(jsonPath("$.providers[0].default_model_name").value("gpt-4o"))
                .andExpect(jsonPath("$.providers[0].configured").value(true))
                .andExpect(jsonPath("$.providers[0].global_max_concurrency").value(4))
                .andExpect(jsonPath("$.providers[0].per_chapter_concurrency").value(1))
                .andExpect(jsonPath("$.providers[0].is_default").value(true));
    }
}
